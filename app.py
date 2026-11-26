

import os
from datetime import date
from functools import wraps

from bson import ObjectId
from bson.errors import InvalidId

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# ==========================================
# 1. CONFIGURACIÓN DE FLASK
# ==========================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "nutrifit_clave_secreta_cambiar"
)


# ==========================================
# 2. CONEXIÓN CON MONGODB
# ==========================================

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://localhost:27017/"
)

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000
)

db = client["nutrifit"]

users = db["users"]
pacientes = db["pacientes"]

# Colección de citas
# Se utiliza un nombre diferente para evitar
# confusiones con las funciones de Flask.

coleccion_citas = db["citas"]

evaluaciones = db["evaluaciones"]


users.create_index(
    "email",
    unique=True
)


# ==========================================
# 3. FUNCIONES AUXILIARES
# ==========================================

def convertir_id(valor):

    try:
        return ObjectId(valor)

    except (InvalidId, TypeError):
        return None


def login_required(funcion):

    @wraps(funcion)
    def decorador(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Inicia sesión para continuar.",
                "warning"
            )

            return redirect(url_for("login"))

        return funcion(*args, **kwargs)

    return decorador


# BUSCAR PACIENTE DEL USUARIO ACTUAL

def obtener_paciente(paciente_id):

    oid = convertir_id(paciente_id)

    if oid is None:
        return None

    return pacientes.find_one({

        "_id": oid,

        "user_id": session["user_id"]

    })


# ==========================================
# 4. PÁGINA PRINCIPAL
# ==========================================

@app.route("/")
@login_required
def index():

    uid = session["user_id"]

    hoy = date.today().isoformat()

    total_pacientes = pacientes.count_documents({

        "user_id": uid

    })

    total_citas = coleccion_citas.count_documents({

        "user_id": uid,

        "fecha": {"$gte": hoy}

    })

    proximas = list(
        coleccion_citas.find({

            "user_id": uid,

            "fecha": {"$gte": hoy}

        }).sort([

            ("fecha", 1),

            ("hora", 1)

        ]).limit(5)
    )

    for cita in proximas:

        paciente = obtener_paciente(
            cita["paciente_id"]
        )

        cita["paciente_nombre"] = (

            paciente["nombre"]
            if paciente
            else "Paciente no disponible"

        )

    return render_template(

        "index.html",

        total_pacientes=total_pacientes,

        total_citas=total_citas,

        proximas=proximas

    )


# ==========================================
# 5. REGISTRO DE USUARIOS
# ==========================================

@app.route("/registro", methods=["GET", "POST"])
def registro():

    if request.method == "POST":

        nombre = request.form.get(
            "nombre", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        confirm_password = request.form.get(
            "confirm_password", ""
        )

        if not nombre or not email or len(password) < 8:

            flash(
                "Completa todos los campos. "
                "La contraseña debe tener mínimo 8 caracteres.",
                "danger"
            )

            return render_template("registro.html")

        if password != confirm_password:

            flash(
                "Las contraseñas no coinciden.",
                "danger"
            )

            return render_template("registro.html")

        try:

            users.insert_one({

                "nombre": nombre,

                "email": email,

                "password_hash": generate_password_hash(
                    password
                )

            })

            flash(
                "Cuenta creada correctamente. "
                "Ya puedes iniciar sesión.",
                "success"
            )

            return redirect(url_for("login"))

        except DuplicateKeyError:

            flash(
                "Ese correo ya está registrado.",
                "danger"
            )

    return render_template("registro.html")


# ==========================================
# 6. INICIAR SESIÓN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        usuario = users.find_one({

            "email": email

        })

        if usuario and check_password_hash(

            usuario["password_hash"],

            password

        ):

            session.clear()

            session["user_id"] = str(
                usuario["_id"]
            )

            session["nombre"] = usuario["nombre"]

            return redirect(url_for("index"))

        flash(
            "Correo o contraseña incorrectos.",
            "danger"
        )

    return render_template("login.html")


# ==========================================
# 7. CERRAR SESIÓN
# ==========================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "Has cerrado sesión.",
        "success"
    )

    return redirect(url_for("login"))


# ==========================================
# 8. LISTA DE PACIENTES
# ==========================================

@app.route("/pacientes")
@login_required
def lista_pacientes():

    lista = list(

        pacientes.find({

            "user_id": session["user_id"]

        }).sort("nombre", 1)

    )

    return render_template(

        "pacientes.html",

        pacientes=lista

    )


# ==========================================
# 9. REGISTRAR PACIENTES
# ==========================================

@app.route("/pacientes/nuevo", methods=["GET", "POST"])
@login_required
def nuevo_paciente():

    if request.method == "POST":

        datos = {

            "user_id": session["user_id"],

            "nombre": request.form.get(
                "nombre", ""
            ).strip(),

            "fecha_nacimiento": request.form.get(
                "fecha_nacimiento", ""
            ),

            "sexo": request.form.get(
                "sexo", ""
            ),

            "telefono": request.form.get(
                "telefono", ""
            ).strip(),

            "email": request.form.get(
                "email", ""
            ).strip(),

            "objetivo": request.form.get(
                "objetivo", ""
            ).strip(),

            "alergias": request.form.get(
                "alergias", ""
            ).strip(),

            "notas": request.form.get(
                "notas", ""
            ).strip(),

            "created_at": date.today().isoformat()

        }

        if not datos["nombre"]:

            flash(
                "El nombre del paciente es obligatorio.",
                "danger"
            )

            return render_template(

                "pacientes_form.html",

                paciente=None

            )

        pacientes.insert_one(datos)

        flash(
            "Paciente registrado correctamente.",
            "success"
        )

        return redirect(
            url_for("lista_pacientes")
        )

    return render_template(

        "pacientes_form.html",

        paciente=None

    )


# ==========================================
# 10. EDITAR PACIENTES
# ==========================================

@app.route(
    "/pacientes/<paciente_id>/editar",
    methods=["GET", "POST"]
)
@login_required
def editar_paciente(paciente_id):

    paciente = obtener_paciente(paciente_id)

    if paciente is None:

        flash(
            "Paciente no encontrado.",
            "danger"
        )

        return redirect(
            url_for("lista_pacientes")
        )

    if request.method == "POST":

        datos = {

            "nombre": request.form.get(
                "nombre", ""
            ).strip(),

            "fecha_nacimiento": request.form.get(
                "fecha_nacimiento", ""
            ),

            "sexo": request.form.get(
                "sexo", ""
            ),

            "telefono": request.form.get(
                "telefono", ""
            ).strip(),

            "email": request.form.get(
                "email", ""
            ).strip(),

            "objetivo": request.form.get(
                "objetivo", ""
            ).strip(),

            "alergias": request.form.get(
                "alergias", ""
            ).strip(),

            "notas": request.form.get(
                "notas", ""
            ).strip()

        }

        if not datos["nombre"]:

            flash(
                "El nombre del paciente es obligatorio.",
                "danger"
            )

            return render_template(

                "pacientes_form.html",

                paciente=paciente

            )

        pacientes.update_one(

            {

                "_id": paciente["_id"],

                "user_id": session["user_id"]

            },

            {

                "$set": datos

            }

        )

        flash(
            "Paciente actualizado correctamente.",
            "success"
        )

        return redirect(
            url_for("lista_pacientes")
        )

    return render_template(

        "pacientes_form.html",

        paciente=paciente

    )


# ==========================================
# 11. DETALLES DEL PACIENTE
# ==========================================

@app.route("/pacientes/<paciente_id>")
@login_required
def detalles_paciente(paciente_id):

    paciente = obtener_paciente(paciente_id)

    if paciente is None:

        flash(
            "Paciente no encontrado.",
            "danger"
        )

        return redirect(
            url_for("lista_pacientes")
        )

    historial = list(

        evaluaciones.find({

            "paciente_id": paciente_id,

            "user_id": session["user_id"]

        }).sort("fecha", -1)

    )

    return render_template(

        "pacientes_detalles.html",

        paciente=paciente,

        evaluaciones=historial

    )


# ==========================================
# 12. AGREGAR EVALUACIÓN NUTRICIONAL
# ==========================================

@app.route(
    "/pacientes/<paciente_id>/evaluaciones",
    methods=["POST"]
)
@login_required
def agregar_evaluacion(paciente_id):

    paciente = obtener_paciente(paciente_id)

    if paciente is None:

        flash(
            "Paciente no encontrado.",
            "danger"
        )

        return redirect(
            url_for("lista_pacientes")
        )

    try:

        peso = request.form.get("peso") or None

        estatura = request.form.get("estatura") or None

        peso = float(peso) if peso else None

        estatura = float(estatura) if estatura else None

        if peso is not None and peso <= 0:
            raise ValueError

        if estatura is not None and estatura <= 0:
            raise ValueError

    except ValueError:

        flash(
            "Introduce un peso y una estatura válidos.",
            "danger"
        )

        return redirect(

            url_for(

                "detalles_paciente",

                paciente_id=paciente_id

            )

        )

    evaluaciones.insert_one({

        "user_id": session["user_id"],

        "paciente_id": paciente_id,

        "fecha": request.form.get(
            "fecha"
        ) or date.today().isoformat(),

        "peso": peso,

        "estatura": estatura,

        "notas": request.form.get(
            "notas", ""
        ).strip()

    })

    flash(
        "Evaluación registrada correctamente.",
        "success"
    )

    return redirect(

        url_for(

            "detalles_paciente",

            paciente_id=paciente_id

        )

    )


# ==========================================
# 13. CITAS Y CONSULTAS
# ==========================================

@app.route("/citas", methods=["GET", "POST"])
@login_required
def citas_pagina():

    uid = session["user_id"]

    if request.method == "POST":

        paciente_id = request.form.get(
            "paciente_id", ""
        ).strip()

        fecha = request.form.get(
            "fecha", ""
        ).strip()

        hora = request.form.get(
            "hora", ""
        ).strip()

        tipo = request.form.get(
            "tipo", ""
        ).strip()

        motivo = request.form.get(
            "motivo", ""
        ).strip()

        # Verificar que el paciente exista
        # y pertenezca al usuario actual.

        paciente = obtener_paciente(paciente_id)

        if not paciente:

            flash(
                "Selecciona un paciente válido.",
                "danger"
            )

        elif not fecha or not hora:

            flash(
                "La fecha y la hora son obligatorias.",
                "danger"
            )

        elif not tipo or not motivo:

            flash(
                "Completa el tipo y el motivo de consulta.",
                "danger"
            )

        else:

            nueva_cita = {

                "user_id": uid,

                "paciente_id": paciente_id,

                "paciente_nombre": paciente["nombre"],

                "fecha": fecha,

                "hora": hora,

                "tipo": tipo,

                "motivo": motivo,

                "estado": "Programada"

            }

            coleccion_citas.insert_one(nueva_cita)

            flash(
                "¡Cita registrada correctamente!",
                "success"
            )

            return redirect(
                url_for("citas_pagina")
            )

    # Obtener pacientes del usuario actual.

    lista_pacientes = list(

        pacientes.find({

            "user_id": uid

        }).sort("nombre", 1)

    )

    # Obtener citas del usuario actual.

    lista_citas = list(

        coleccion_citas.find({

            "user_id": uid

        }).sort([

            ("fecha", 1),

            ("hora", 1)

        ])

    )

    # Mostrar el nombre actualizado del paciente.

    for cita in lista_citas:

        paciente = obtener_paciente(
            cita.get("paciente_id", "")
        )

        cita["paciente_nombre"] = (

            paciente["nombre"]
            if paciente
            else cita.get(
                "paciente_nombre",
                "Paciente no disponible"
            )

        )

    return render_template(

        "citas.html",

        pacientes=lista_pacientes,

        citas=lista_citas

    )


# ==========================================
# 14. ELIMINAR CITAS
# ==========================================

@app.route(
    "/citas/<cita_id>/eliminar",
    methods=["POST"]
)
@login_required
def eliminar_cita(cita_id):

    oid = convertir_id(cita_id)

    if oid is None:

        flash(
            "Identificador de cita inválido.",
            "danger"
        )

        return redirect(
            url_for("citas_pagina")
        )

    resultado = coleccion_citas.delete_one({

        "_id": oid,

        "user_id": session["user_id"]

    })

    if resultado.deleted_count:

        flash(
            "Cita eliminada correctamente.",
            "success"
        )

    else:

        flash(
            "No se encontró la cita.",
            "danger"
        )

    return redirect(
        url_for("citas_pagina")
    )


# ==========================================
# 15. EJECUTAR APLICACIÓN
# ==========================================

if __name__ == "__main__":

    app.run(

        debug=True,

        host="127.0.0.1",

        port=5000

    )
