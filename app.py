from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, date
import sqlite3
import os
import re

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cabanas-intiyaco-secret-2024')

TIPO_CAMBIO = float(os.environ.get('TIPO_CAMBIO', '1200'))

CABANAS = {
    'cedro': {
        'nombre': 'El Cedro',
        'capacidad': 4,
        'precio_usd': 100,
        'descripcion': 'Acogedora cabaña para hasta 4 personas, rodeada de naturaleza. Cuenta con cocina equipada, living comedor, 2 dormitorios y baño completo.',
        'amenities': ['WiFi', 'Cocina equipada', 'Parrilla', 'Estacionamiento', 'Ropa de cama', 'Calefacción'],
        'imagen': 'https://images.unsplash.com/photo-1449158743715-0a90ebb6d2d8?w=800&q=80',
        'imagen2': 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800&q=80',
    },
    'tabaquillo': {
        'nombre': 'El Tabaquillo',
        'capacidad': 6,
        'precio_usd': 120,
        'descripcion': 'Espaciosa cabaña premium para hasta 6 personas, ideal para familias grandes o grupos de amigos. 3 dormitorios, 2 baños y amplias áreas de esparcimiento.',
        'amenities': ['WiFi', 'Cocina equipada', 'Parrilla', 'Estacionamiento', 'Ropa de cama', 'Calefacción', 'Quincho', 'Pileta'],
        'imagen': 'https://images.unsplash.com/photo-1510798831971-661eb04b3739?w=800&q=80',
        'imagen2': 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=800&q=80',
    }
}

RESENAS = [
    {'nombre': 'María G.', 'estrellas': 5, 'texto': 'Increíble lugar, muy tranquilo y limpio. Volvería sin dudarlo.', 'cabana': 'cedro'},
    {'nombre': 'Carlos P.', 'estrellas': 5, 'texto': 'La cabaña estaba perfecta. El entorno es hermoso, ideal para desconectarse.', 'cabana': 'tabaquillo'},
    {'nombre': 'Laura M.', 'estrellas': 4, 'texto': 'Muy buena experiencia, excelente atención y todo muy cómodo.', 'cabana': 'cedro'},
    {'nombre': 'Roberto S.', 'estrellas': 5, 'texto': 'Fuimos 6 amigos y quedamos encantados. La pileta y el quincho son un lujo.', 'cabana': 'tabaquillo'},
]

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'cabanas.db')
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'lacho2024!')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS reservas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cabana_id TEXT NOT NULL,
        nombre TEXT NOT NULL,
        apellido TEXT NOT NULL,
        dni TEXT NOT NULL,
        email TEXT,
        telefono TEXT,
        fecha_ingreso TEXT NOT NULL,
        fecha_salida TEXT NOT NULL,
        noches INTEGER NOT NULL,
        precio_noche_usd REAL NOT NULL,
        total_usd REAL NOT NULL,
        total_ars REAL NOT NULL,
        deposito_usd REAL NOT NULL,
        moneda TEXT DEFAULT 'USD',
        estado TEXT DEFAULT 'pendiente',
        pago_deposito INTEGER DEFAULT 0,
        notas TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()


init_db()


def validar_dni(dni):
    dni_limpio = re.sub(r'[\.\-\s]', '', dni)
    return dni_limpio.isdigit() and 7 <= len(dni_limpio) <= 9


def validar_fechas(f_ingreso, f_salida):
    hoy = date.today()
    if f_ingreso < hoy:
        return False, 'La fecha de ingreso no puede ser en el pasado'
    if f_salida <= f_ingreso:
        return False, 'La fecha de salida debe ser posterior al ingreso'
    return True, ''


def cabana_disponible(cabana_id, f_ingreso, f_salida, excluir_id=None):
    conn = get_db()
    query = '''SELECT id FROM reservas 
               WHERE cabana_id = ? AND estado != 'cancelada'
               AND fecha_ingreso < ? AND fecha_salida > ?'''
    params = [cabana_id, f_salida.strftime('%Y-%m-%d'), f_ingreso.strftime('%Y-%m-%d')]
    if excluir_id:
        query += ' AND id != ?'
        params.append(excluir_id)
    resultado = conn.execute(query, params).fetchone()
    conn.close()
    return resultado is None


@app.route('/')
def index():
    return render_template('index.html', cabanas=CABANAS, resenas=RESENAS)


@app.route('/cabana/<cabana_id>')
def detalle_cabana(cabana_id):
    if cabana_id not in CABANAS:
        return redirect(url_for('index'))
    cabana = CABANAS[cabana_id]
    resenas = [r for r in RESENAS if r['cabana'] == cabana_id]
    return render_template('cabana.html', cabana=cabana, cabana_id=cabana_id,
                           resenas=resenas, tipo_cambio=TIPO_CAMBIO)


@app.route('/reservar/<cabana_id>', methods=['GET', 'POST'])
def reservar(cabana_id):
    if cabana_id not in CABANAS:
        return redirect(url_for('index'))
    cabana = CABANAS[cabana_id]
    error = None

    if request.method == 'POST':
        nombre   = request.form.get('nombre', '').strip()
        apellido = request.form.get('apellido', '').strip()
        dni      = request.form.get('dni', '').strip()
        email    = request.form.get('email', '').strip()
        telefono = request.form.get('telefono', '').strip()
        f_ing_str = request.form.get('fecha_ingreso', '')
        f_sal_str = request.form.get('fecha_salida', '')
        moneda   = request.form.get('moneda', 'USD')

        if not all([nombre, apellido, dni, f_ing_str, f_sal_str]):
            error = 'Completá todos los campos obligatorios'
        elif not validar_dni(dni):
            error = 'El DNI debe contener solo números (7 a 9 dígitos)'
        else:
            try:
                f_ingreso = datetime.strptime(f_ing_str, '%Y-%m-%d').date()
                f_salida  = datetime.strptime(f_sal_str, '%Y-%m-%d').date()
                ok, msg = validar_fechas(f_ingreso, f_salida)
                if not ok:
                    error = msg
                elif not cabana_disponible(cabana_id, f_ingreso, f_salida):
                    error = 'La cabaña no está disponible en esas fechas. Por favor elegí otras fechas.'
                else:
                    noches = (f_salida - f_ingreso).days
                    precio = cabana['precio_usd']
                    total_usd = noches * precio
                    total_ars = total_usd * TIPO_CAMBIO
                    deposito_usd = total_usd * 0.5
                    dni_limpio = re.sub(r'[\.\-\s]', '', dni)

                    conn = get_db()
                    conn.execute('''INSERT INTO reservas 
                        (cabana_id, nombre, apellido, dni, email, telefono,
                         fecha_ingreso, fecha_salida, noches, precio_noche_usd,
                         total_usd, total_ars, deposito_usd, moneda)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (cabana_id, nombre, apellido, dni_limpio, email, telefono,
                         f_ing_str, f_sal_str, noches, precio,
                         total_usd, total_ars, deposito_usd, moneda))
                    conn.commit()
                    reserva_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
                    conn.close()
                    return redirect(url_for('exito', reserva_id=reserva_id))
            except ValueError:
                error = 'Formato de fecha inválido'

    return render_template('reservar.html', cabana=cabana, cabana_id=cabana_id,
                           error=error, tipo_cambio=TIPO_CAMBIO,
                           hoy=date.today().strftime('%Y-%m-%d'))


@app.route('/exito/<int:reserva_id>')
def exito(reserva_id):
    conn = get_db()
    reserva = conn.execute('SELECT * FROM reservas WHERE id = ?', (reserva_id,)).fetchone()
    conn.close()
    if not reserva:
        return redirect(url_for('index'))
    cabana = CABANAS.get(reserva['cabana_id'], {})
    return render_template('exito.html', reserva=reserva, cabana=cabana, tipo_cambio=TIPO_CAMBIO)


# ── ADMIN ──────────────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('usuario') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session['admin'] = True
            return redirect(url_for('admin_panel'))
        return render_template('admin_login.html', error='Usuario o contraseña incorrectos')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/admin')
@admin_required
def admin_panel():
    conn = get_db()
    filtro = request.args.get('filtro', 'todas')
    cabana_f = request.args.get('cabana', 'todas')
    query = 'SELECT * FROM reservas WHERE 1=1'
    params = []
    if filtro == 'pendientes':
        query += " AND estado = 'pendiente'"
    elif filtro == 'confirmadas':
        query += " AND estado = 'confirmada'"
    elif filtro == 'canceladas':
        query += " AND estado = 'cancelada'"
    if cabana_f != 'todas':
        query += ' AND cabana_id = ?'
        params.append(cabana_f)
    query += ' ORDER BY created_at DESC'
    reservas = conn.execute(query, params).fetchall()
    total_usd = conn.execute("SELECT SUM(total_usd) FROM reservas WHERE estado != 'cancelada'").fetchone()[0] or 0
    pendientes = conn.execute("SELECT COUNT(*) FROM reservas WHERE estado = 'pendiente'").fetchone()[0]
    confirmadas = conn.execute("SELECT COUNT(*) FROM reservas WHERE estado = 'confirmada'").fetchone()[0]
    conn.close()
    # Pasar todas las reservas como JSON para el calendario
    import json as _json
    conn2 = get_db()
    todas_reservas_raw = conn2.execute('SELECT cabana_id, nombre, apellido, fecha_ingreso, fecha_salida, noches, estado FROM reservas').fetchall()
    conn2.close()
    reservas_json = _json.dumps([dict(r) for r in todas_reservas_raw])

    return render_template('admin.html', reservas=reservas, cabanas=CABANAS,
                           total_usd=total_usd, pendientes=pendientes,
                           confirmadas=confirmadas, filtro=filtro, cabana_f=cabana_f,
                           reservas_json=reservas_json)


@app.route('/admin/accion/<int:reserva_id>/<accion>', methods=['POST'])
@admin_required
def admin_accion(reserva_id, accion):
    conn = get_db()
    if accion == 'confirmar':
        conn.execute("UPDATE reservas SET estado='confirmada' WHERE id=?", (reserva_id,))
    elif accion == 'cancelar':
        conn.execute("UPDATE reservas SET estado='cancelada' WHERE id=?", (reserva_id,))
    elif accion == 'pago_deposito':
        conn.execute("UPDATE reservas SET pago_deposito=1 WHERE id=?", (reserva_id,))
    elif accion == 'pago_total':
        conn.execute("UPDATE reservas SET pago_deposito=1, estado='confirmada' WHERE id=?", (reserva_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/admin/notas/<int:reserva_id>', methods=['POST'])
@admin_required
def admin_notas(reserva_id):
    notas = request.form.get('notas', '')
    conn = get_db()
    conn.execute('UPDATE reservas SET notas=? WHERE id=?', (notas, reserva_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))


if __name__ == '__main__':
    app.run(debug=True)