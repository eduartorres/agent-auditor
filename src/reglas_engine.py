import re


# Motor de reglas deterministas del Agente Auditor.
# Este módulo evalúa cada caso contra las reglas de negocio definidas en reglas.json.
# Las decisiones aquí son binarias e irrefutables: o hay violación o no la hay.
# No hay ambigüedad — eso es responsabilidad del módulo de fidelidad semántica.


def verificar_bloqueo_cumplimiento(contexto: str, palabras_clave: list) -> dict:
    """
    Detecta si el contexto RAG contiene alertas de cumplimiento crítico,
    como flags SARLAFT, AML u otras listas restrictivas.

    Este control es el de mayor severidad en el sistema. Una coincidencia
    aquí anula cualquier otra evaluación y bloquea la transacción.
    """
    contexto_lower = contexto.lower()

    for palabra in palabras_clave:
        if palabra.lower() in contexto_lower:
            return {
                "violacion": True,
                "tipo": "BLOQUEO_CUMPLIMIENTO",
                "detalle": f"Contexto contiene alerta crítica de cumplimiento: '{palabra}'"
            }

    return {"violacion": False}


def verificar_limite_cobertura_auto(contexto: str, respuesta: str, config: dict) -> dict:
    """
    Valida que el monto aprobado para cobertura de cristales no supere
    el límite definido en la póliza y que el deducible haya sido considerado.

    Extrae valores numéricos del texto mediante expresiones regulares
    para hacer una validación matemática real, no solo semántica.
    """
    config_cristales = config["limites_cobertura"]["cristales_auto"]
    cobertura_maxima = config_cristales["cobertura_maxima_usd"]
    deducible = config_cristales["deducible_porcentaje"]

    # Solo aplica si el contexto menciona cobertura de cristales o parabrisas
    if not any(k in contexto.lower() for k in ["cristales", "parabrisas", "global auto"]):
        return {"violacion": False}

    # Extrae el monto aprobado de la respuesta del agente
    montos = re.findall(r"\$([0-9,]+(?:\.[0-9]+)?)", respuesta)

    if not montos:
        return {
            "violacion": True,
            "tipo": "MONTO_NO_IDENTIFICABLE",
            "detalle": "No fue posible extraer el monto aprobado de la respuesta del agente"
        }

    monto_aprobado = float(montos[0].replace(",", ""))
    monto_neto = monto_aprobado * (1 - deducible)

    # Validación 1: el monto bruto no debe superar la cobertura máxima
    if monto_aprobado > cobertura_maxima:
        return {
            "violacion": True,
            "tipo": "LIMITE_COBERTURA_EXCEDIDO",
            "detalle": (
                f"Monto aprobado ${monto_aprobado:,.2f} USD supera la cobertura "
                f"máxima de ${cobertura_maxima:,.2f} USD"
            )
        }

    # Validación 2: verificar que el deducible fue mencionado en la respuesta
    menciona_deducible = "deducible" in respuesta.lower()

    return {
        "violacion": False,
        "monto_aprobado": monto_aprobado,
        "deducible_aplicado": deducible,
        "monto_neto_asegurado": round(monto_neto, 2),
        "deducible_mencionado": menciona_deducible,
        "detalle": (
            f"Monto ${monto_aprobado:,.2f} USD dentro del límite. "
            f"Deducible 10% = ${monto_aprobado * deducible:,.2f} USD. "
            f"Neto a pagar: ${monto_neto:,.2f} USD"
        )
    }


def verificar_limite_vida(contexto: str, respuesta: str, config: dict) -> dict:
    """
    Valida que la emisión de pólizas de vida respete el límite automático
    para asegurados mayores de la edad umbral definida en configuración.

    Si el monto supera el límite o el asegurado supera la edad límite,
    la emisión automática no está permitida y requiere exámenes médicos.
    """
    config_vida = config["limites_cobertura"]["vida_individual_emision_automatica"]
    monto_maximo = config_vida["monto_maximo_usd"]
    edad_limite = config_vida["edad_limite"]

    # Solo aplica si el contexto menciona póliza de vida
    if "vida" not in contexto.lower():
        return {"violacion": False}

    # Extrae montos de la respuesta
    montos = re.findall(r"\$([0-9,]+(?:\.[0-9]+)?)", respuesta)

    if not montos:
        return {"violacion": False}

    monto_aprobado = float(montos[0].replace(",", ""))

    # Extrae la edad mencionada en la respuesta si existe
    edades = re.findall(r"\b(\d{2})\s*años", respuesta)
    edad_asegurado = int(edades[0]) if edades else None

    # Violación por monto
    if monto_aprobado > monto_maximo:
        detalle = (
            f"Monto aprobado ${monto_aprobado:,.2f} USD supera el límite de "
            f"emisión automática de ${monto_maximo:,.2f} USD"
        )

        # Agrava la violación si además el asegurado supera la edad límite
        if edad_asegurado and edad_asegurado > edad_limite:
            detalle += (
                f". Asegurado de {edad_asegurado} años supera el límite de "
                f"{edad_limite} años para emisión automática. "
                f"Se requieren exámenes médicos obligatorios"
            )

        return {
            "violacion": True,
            "tipo": "LIMITE_EMISION_VIDA_EXCEDIDO",
            "monto_aprobado": monto_aprobado,
            "monto_maximo": monto_maximo,
            "edad_asegurado": edad_asegurado,
            "detalle": detalle
        }

    return {"violacion": False}


def verificar_cuenta_sospechosa(contexto: str, respuesta: str, config: dict) -> dict:
    """
    Detecta si el contexto marca la cuenta como sospechosa de abuso
    y valida que el agente haya derivado el caso a revisión manual
    en lugar de procesarlo automáticamente.
    """
    palabras_riesgo = config["alertas_riesgo"]["siniestros_recientes"]["palabras_clave"]
    contexto_lower = contexto.lower()

    es_cuenta_sospechosa = any(p.lower() in contexto_lower for p in palabras_riesgo)

    if not es_cuenta_sospechosa:
        return {"violacion": False}

    # Si la cuenta es sospechosa, el agente debe haber derivado el caso
    respuesta_lower = respuesta.lower()
    terminos_derivacion = ["analista", "revisión", "no puedo procesar", "contactará"]
    derivo_correctamente = any(t in respuesta_lower for t in terminos_derivacion)

    if derivo_correctamente:
        return {
            "violacion": False,
            "detalle": "Cuenta sospechosa identificada. El agente derivó correctamente a revisión manual"
        }

    return {
        "violacion": True,
        "tipo": "PROCESAMIENTO_CUENTA_SOSPECHOSA",
        "detalle": "El agente procesó automáticamente una cuenta marcada como sospechosa de abuso"
    }


def evaluar_reglas(caso: dict, config: dict) -> dict:
    """
    Punto de entrada principal del motor de reglas.
    Ejecuta todos los controles sobre un caso y retorna el resultado
    consolidado con la violación más grave encontrada.

    El orden de evaluación importa: las violaciones de cumplimiento
    tienen prioridad absoluta sobre cualquier otro control.
    """
    contexto = caso["contexto_rag"]
    respuesta = caso["respuesta_agent_b"]

    # Control 1: Cumplimiento regulatorio (máxima prioridad)
    resultado_cumplimiento = verificar_bloqueo_cumplimiento(
        contexto,
        config["alertas_criticas"]["palabras_clave_bloqueo"]
    )
    if resultado_cumplimiento["violacion"]:
        return {
            "tiene_violacion": True,
            "severidad": "CRITICA",
            "resultado": resultado_cumplimiento
        }

    # Control 2: Límite de cobertura auto
    resultado_auto = verificar_limite_cobertura_auto(contexto, respuesta, config)
    if resultado_auto["violacion"]:
        return {
            "tiene_violacion": True,
            "severidad": "ALTA",
            "resultado": resultado_auto
        }

    # Control 3: Límite de emisión de vida
    resultado_vida = verificar_limite_vida(contexto, respuesta, config)
    if resultado_vida["violacion"]:
        return {
            "tiene_violacion": True,
            "severidad": "ALTA",
            "resultado": resultado_vida
        }

    # Control 4: Cuenta bajo sospecha de abuso
    resultado_sospecha = verificar_cuenta_sospechosa(contexto, respuesta, config)
    if resultado_sospecha["violacion"]:
        return {
            "tiene_violacion": True,
            "severidad": "MEDIA",
            "resultado": resultado_sospecha
        }

    # Sin violaciones detectadas — se pasa el control al módulo semántico
    detalle_auto = resultado_auto.get("detalle", "")
    detalle_sospecha = resultado_sospecha.get("detalle", "")
    detalle = detalle_auto or detalle_sospecha or "Sin violaciones de reglas de negocio detectadas"

    return {
        "tiene_violacion": False,
        "severidad": "NINGUNA",
        "resultado": {"detalle": detalle}
    }
