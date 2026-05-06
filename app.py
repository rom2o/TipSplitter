from flask import Flask, render_template, request, jsonify, session, Response
import os
import csv
import io
from datetime import date, timedelta, datetime
from flask_sqlalchemy import SQLAlchemy
from functools import wraps

app = Flask(__name__)

CARD_DEDUCTION = 0.30

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///tips.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

APP_PIN = os.environ.get('APP_PIN', '1234').strip()

db = SQLAlchemy(app)


class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    active = db.Column(db.Boolean, default=True)


class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.String(10), nullable=False)
    day = db.Column(db.Integer, nullable=False)
    shift_type = db.Column(db.String(10), nullable=False)
    cash_tips = db.Column(db.Float, default=0)
    card_tips = db.Column(db.Float, default=0)
    workers = db.relationship('ShiftStaff', backref='shift', cascade='all, delete-orphan')


class ShiftStaff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)


class DayNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.String(10), nullable=False)
    day = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Text, default='')
    __table_args__ = (db.UniqueConstraint('week_start', 'day'),)


with app.app_context():
    db.create_all()
    if Staff.query.count() == 0:
        for name in ['Green', 'Beau', 'Julien', 'Tun', 'Beam', 'Jay']:
            db.session.add(Staff(name=name, active=True))
        db.session.commit()


# ── Auth ───────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/api/check-auth')
def check_auth():
    return jsonify({'authenticated': bool(session.get('authenticated'))})


@app.route('/api/login', methods=['POST'])
def login():
    pin = (request.json or {}).get('pin', '')
    if pin == APP_PIN:
        session['authenticated'] = True
        return jsonify({'ok': True})
    return jsonify({'error': 'Wrong PIN'}), 401


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


# ── Staff ──────────────────────────────────────────────────────────────────────

@app.route('/api/staff', methods=['GET'])
@login_required
def get_staff():
    staff = Staff.query.filter_by(active=True).order_by(Staff.name).all()
    return jsonify([{'id': s.id, 'name': s.name} for s in staff])


@app.route('/api/staff', methods=['POST'])
@login_required
def add_staff():
    name = (request.json or {}).get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    existing = Staff.query.filter(Staff.name.ilike(name)).first()
    if existing:
        existing.active = True
        db.session.commit()
        return jsonify({'id': existing.id, 'name': existing.name})
    s = Staff(name=name, active=True)
    db.session.add(s)
    db.session.commit()
    return jsonify({'id': s.id, 'name': s.name})


@app.route('/api/staff/<int:staff_id>', methods=['DELETE'])
@login_required
def remove_staff(staff_id):
    s = Staff.query.get_or_404(staff_id)
    s.active = False
    db.session.commit()
    return jsonify({'ok': True})


# ── Shifts ─────────────────────────────────────────────────────────────────────

@app.route('/api/week/<week_start>', methods=['GET'])
@login_required
def get_week(week_start):
    shifts = Shift.query.filter_by(week_start=week_start).all()
    notes = DayNote.query.filter_by(week_start=week_start).all()
    result = {}
    for shift in shifts:
        key = f"{shift.day}_{shift.shift_type}"
        result[key] = {
            'id': shift.id,
            'cash_tips': shift.cash_tips,
            'card_tips': shift.card_tips,
            'staff': [ss.staff_id for ss in shift.workers]
        }
    for n in notes:
        result[f"note_{n.day}"] = n.note
    return jsonify(result)


@app.route('/api/shift', methods=['POST'])
@login_required
def save_shift():
    data = request.json or {}
    week_start = data['week_start']
    day = int(data['day'])
    shift_type = data['shift_type']
    cash_tips = float(data.get('cash_tips', 0) or 0)
    card_tips = float(data.get('card_tips', 0) or 0)
    staff_ids = data.get('staff_ids', [])

    shift = Shift.query.filter_by(week_start=week_start, day=day, shift_type=shift_type).first()
    if shift:
        shift.cash_tips = cash_tips
        shift.card_tips = card_tips
        ShiftStaff.query.filter_by(shift_id=shift.id).delete()
    else:
        shift = Shift(week_start=week_start, day=day, shift_type=shift_type,
                      cash_tips=cash_tips, card_tips=card_tips)
        db.session.add(shift)
        db.session.flush()

    for sid in staff_ids:
        db.session.add(ShiftStaff(shift_id=shift.id, staff_id=int(sid)))

    db.session.commit()
    return jsonify({'ok': True})


# ── Clear day ─────────────────────────────────────────────────────────────────

@app.route('/api/day/<week_start>/<int:day>', methods=['DELETE'])
@login_required
def clear_day(week_start, day):
    shifts = Shift.query.filter_by(week_start=week_start, day=day).all()
    for shift in shifts:
        ShiftStaff.query.filter_by(shift_id=shift.id).delete()
        db.session.delete(shift)
    DayNote.query.filter_by(week_start=week_start, day=day).delete()
    db.session.commit()
    return jsonify({'ok': True})


# ── Notes ──────────────────────────────────────────────────────────────────────

@app.route('/api/note', methods=['POST'])
@login_required
def save_note():
    data = request.json or {}
    week_start = data['week_start']
    day = int(data['day'])
    note = data.get('note', '').strip()

    existing = DayNote.query.filter_by(week_start=week_start, day=day).first()
    if existing:
        existing.note = note
    else:
        db.session.add(DayNote(week_start=week_start, day=day, note=note))
    db.session.commit()
    return jsonify({'ok': True})


# ── Summary ────────────────────────────────────────────────────────────────────

@app.route('/api/summary/<week_start>', methods=['GET'])
@login_required
def get_summary(week_start):
    shifts = Shift.query.filter_by(week_start=week_start).all()
    staff_list = Staff.query.filter_by(active=True).all()
    notes = DayNote.query.filter_by(week_start=week_start).all()

    totals = {s.id: {'name': s.name, 'cash': 0.0, 'card': 0.0, 'shifts': 0} for s in staff_list}

    for shift in shifts:
        worker_ids = [ss.staff_id for ss in shift.workers]
        if not worker_ids:
            continue
        cash_per = shift.cash_tips / len(worker_ids)
        card_per = shift.card_tips * (1 - CARD_DEDUCTION) / len(worker_ids)
        for sid in worker_ids:
            if sid in totals:
                totals[sid]['cash'] += cash_per
                totals[sid]['card'] += card_per
                totals[sid]['shifts'] += 1

    result = sorted(totals.values(), key=lambda x: -(x['cash'] + x['card']))
    notes_list = [{'day': n.day, 'note': n.note} for n in notes if n.note]
    return jsonify({'staff': result, 'week_start': week_start, 'notes': notes_list})


# ── History ────────────────────────────────────────────────────────────────────

@app.route('/api/weeks', methods=['GET'])
@login_required
def get_weeks():
    weeks = (db.session.query(Shift.week_start)
             .distinct()
             .order_by(Shift.week_start.desc())
             .all())
    return jsonify([w[0] for w in weeks])


# ── CSV Export ─────────────────────────────────────────────────────────────────

@app.route('/api/export/csv/<week_start>')
@login_required
def export_csv(week_start):
    DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    shifts = Shift.query.filter_by(week_start=week_start).all()
    staff_list = Staff.query.filter_by(active=True).all()
    notes = {n.day: n.note for n in DayNote.query.filter_by(week_start=week_start).all()}

    totals = {s.id: {'name': s.name, 'cash': 0.0, 'card': 0.0, 'shifts': 0} for s in staff_list}
    day_details = {}

    for shift in shifts:
        worker_ids = [ss.staff_id for ss in shift.workers]
        if not worker_ids:
            continue
        cash_per = shift.cash_tips / len(worker_ids)
        card_per = shift.card_tips * (1 - CARD_DEDUCTION) / len(worker_ids)
        for sid in worker_ids:
            if sid in totals:
                totals[sid]['cash'] += cash_per
                totals[sid]['card'] += card_per
                totals[sid]['shifts'] += 1

        key = (shift.day, shift.shift_type)
        workers_names = [s.name for s in staff_list if s.id in worker_ids]
        day_details[key] = {
            'cash': shift.cash_tips,
            'card': shift.card_tips,
            'distributed': distributable,
            'workers': workers_names,
            'per_person': per_person
        }

    monday = datetime.strptime(week_start, '%Y-%m-%d')
    sunday = monday + timedelta(days=6)
    week_label = f"{monday.strftime('%d %b')} - {sunday.strftime('%d %b %Y')}"

    output = io.StringIO()
    w = csv.writer(output)

    w.writerow(['TIP SUMMARY', week_label])
    w.writerow([])
    w.writerow(['Staff', 'Shifts Worked', 'Cash Owed', 'Card Owed (after 30%)', 'Total Owed'])
    for person in sorted(totals.values(), key=lambda x: -(x['cash'] + x['card'])):
        if person['cash'] + person['card'] > 0:
            total_p = person['cash'] + person['card']
            w.writerow([person['name'], person['shifts'], f"${person['cash']:.2f}", f"${person['card']:.2f}", f"${total_p:.2f}"])
    total_cash = sum(p['cash'] for p in totals.values())
    total_card = sum(p['card'] for p in totals.values())
    w.writerow(['', 'TOTAL', f"${total_cash:.2f}", f"${total_card:.2f}", f"${total_cash + total_card:.2f}"])

    w.writerow([])
    w.writerow(['DAILY BREAKDOWN'])
    w.writerow(['Day', 'Shift', 'Cash Tips', 'Card Tips', 'Distributed', 'Per Person', 'Staff', 'Notes'])
    for day_idx in range(7):
        for shift_type in ['lunch', 'dinner']:
            detail = day_details.get((day_idx, shift_type))
            if detail:
                w.writerow([
                    DAYS[day_idx],
                    shift_type.capitalize(),
                    f"${detail['cash']:.2f}",
                    f"${detail['card']:.2f}",
                    f"${detail['distributed']:.2f}",
                    f"${detail['per_person']:.2f}",
                    ', '.join(detail['workers']),
                    notes.get(day_idx, '')
                ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=tips_{week_start}.csv'}
    )


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
