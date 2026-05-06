from flask import Flask, render_template, request, jsonify
import os
from datetime import date, timedelta
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

CARD_DEDUCTION = 0.30

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///tips.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    active = db.Column(db.Boolean, default=True)


class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD (Monday)
    day = db.Column(db.Integer, nullable=False)             # 0=Mon … 6=Sun
    shift_type = db.Column(db.String(10), nullable=False)  # 'lunch' or 'dinner'
    cash_tips = db.Column(db.Float, default=0)
    card_tips = db.Column(db.Float, default=0)
    workers = db.relationship('ShiftStaff', backref='shift', cascade='all, delete-orphan')


class ShiftStaff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)


with app.app_context():
    db.create_all()
    if Staff.query.count() == 0:
        for name in ['Green', 'Beau', 'Julien', 'Tun', 'Beam', 'Jay']:
            db.session.add(Staff(name=name, active=True))
        db.session.commit()


# ── Staff ──────────────────────────────────────────────────────────────────────

@app.route('/api/staff', methods=['GET'])
def get_staff():
    staff = Staff.query.filter_by(active=True).order_by(Staff.name).all()
    return jsonify([{'id': s.id, 'name': s.name} for s in staff])


@app.route('/api/staff', methods=['POST'])
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
def remove_staff(staff_id):
    s = Staff.query.get_or_404(staff_id)
    s.active = False
    db.session.commit()
    return jsonify({'ok': True})


# ── Shifts ─────────────────────────────────────────────────────────────────────

@app.route('/api/week/<week_start>', methods=['GET'])
def get_week(week_start):
    shifts = Shift.query.filter_by(week_start=week_start).all()
    result = {}
    for shift in shifts:
        key = f"{shift.day}_{shift.shift_type}"
        result[key] = {
            'id': shift.id,
            'cash_tips': shift.cash_tips,
            'card_tips': shift.card_tips,
            'staff': [ss.staff_id for ss in shift.workers]
        }
    return jsonify(result)


@app.route('/api/shift', methods=['POST'])
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


# ── Summary ────────────────────────────────────────────────────────────────────

@app.route('/api/summary/<week_start>', methods=['GET'])
def get_summary(week_start):
    shifts = Shift.query.filter_by(week_start=week_start).all()
    staff_list = Staff.query.filter_by(active=True).all()

    totals = {s.id: {'name': s.name, 'amount': 0.0, 'shifts': 0} for s in staff_list}

    for shift in shifts:
        worker_ids = [ss.staff_id for ss in shift.workers]
        if not worker_ids:
            continue
        distributable = shift.cash_tips + shift.card_tips * (1 - CARD_DEDUCTION)
        per_person = distributable / len(worker_ids)
        for sid in worker_ids:
            if sid in totals:
                totals[sid]['amount'] += per_person
                totals[sid]['shifts'] += 1

    result = sorted(totals.values(), key=lambda x: -x['amount'])
    return jsonify({'staff': result, 'week_start': week_start})


# ── History ────────────────────────────────────────────────────────────────────

@app.route('/api/weeks', methods=['GET'])
def get_weeks():
    weeks = (db.session.query(Shift.week_start)
             .distinct()
             .order_by(Shift.week_start.desc())
             .all())
    return jsonify([w[0] for w in weeks])


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
