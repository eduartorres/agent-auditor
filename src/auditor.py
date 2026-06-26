import json
import os
from datetime import datetime

from reglas_engine import evaluar_reglas
from fidelidad import evaluar_fidelidad


# Agente Auditor — orquestador principal.
# Este script es el punto de entrada del sistema. Lee los casos de entrada,
# coordina la evaluación determinista y semántica, genera el diagnóstico
# con el formato requerido y persiste el reporte de auditoría.


def cargar_json(ruta: str) -> dict | list:
    """
    Carga un archivo JSON desde disco con manejo explícito de errores.
    Separar la carga del procesamiento facilita el testing y el debug.
    """
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No se encontró el archivo requerido: {ruta}")

    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def determinar_estado(resultado_reglas: dict, score_final: float, config: dict) -> str:
    """
    Consolida el estado final de la transacción combinando el resultado
    del motor de reglas y el índice de fidelidad semántica.

    La lógica de prioridad es:
      1. Violaciones críticas (SARLAFT, AML) → siempre BLOQUEADO
      2. Violaciones altas (límites de negocio) → siempre RECHAZADO
      3. Sin violación pero score bajo → APROBADO CON ALERTA
      4. Sin violación y score aceptable → APROBADO
    """
    estados = config["estados_transaccion"]

    if not resultado_reglas["tiene_violacion"]:
        umbral_minimo = config["umbrales_fidelidad"]["score_minimo_aceptable"]
        if score_final < umbral_minimo:
            return estados["aprobado_con_alerta"]
        return estados["aprobado"]

    severidad = resultado_reglas["severidad"]

    if severidad == "CRITICA":
        return estados["bloqueado"]

    return estados["rechazado"]


def construir_diagnostico(caso: dict, resultado_reglas: dict, resultado_fidelidad: dict, config: dict) -> dict:
    """
    Ensambla el diagnóstico completo de un caso integrando los resultados
    de ambas capas de evaluación. Este es el objeto que se imprime en consola
    y se persiste en el reporte de auditoría.
    """
    id_caso = caso["id_caso"]
    score_final = resultado_fidelidad["score_final"]
    estado = determinar_estado(resultado_reglas, score_final, config)

    # La razón del diagnóstico prioriza la violación de regla cuando existe,
    # y cae en la interpretación semántica cuando no hay violación detectada
    if resultado_reglas["tiene_violacion"]:
        razon = resultado_reglas["resultado"].get("detalle", "Violación de regla de negocio detectada")
    else:
        razon = resultado_fidelidad["interpretacion"]
        detalle_regla = resultado_reglas["resultado"].get("detalle", "")
        if detalle_regla:
            razon = f"{detalle_regla}. {razon}"

    return {
        "id_caso": id_caso,
        "estado": estado,
        "indice_fidelidad_analitica": score_final,
        "score_semantico_base": resultado_fidelidad["score_base"],
        "severidad_regla": resultado_reglas["severidad"],
        "diagnostico": razon,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


def imprimir_diagnostico(diagnostico: dict) -> None:
    """
    Imprime el diagnóstico en consola con el formato exacto requerido por el reto.
    El formato es fijo para garantizar legibilidad en la demo y consistencia
    con lo que el comité espera ver en pantalla.
    """
    print(f"\nCaso {diagnostico['id_caso']}: {diagnostico['estado']}")
    print(f"  - Indice de Fidelidad Analitica: {diagnostico['indice_fidelidad_analitica']}")
    print(f"  - Diagnostico/Razon: {diagnostico['diagnostico']}")


def guardar_reporte(diagnosticos: list, ruta_salida: str) -> None:
    """
    Persiste el reporte completo de auditoría en formato JSON.
    El archivo generado simula un log real que en producción alimentaría
    un data warehouse o sistema de monitoreo centralizado.
    """
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)

    reporte = {
        "fecha_ejecucion": datetime.utcnow().isoformat() + "Z",
        "total_casos": len(diagnosticos),
        "resumen": {
            "bloqueados": sum(1 for d in diagnosticos if "BLOQUEADO" in d["estado"]),
            "rechazados": sum(1 for d in diagnosticos if "RECHAZADO" in d["estado"]),
            "con_alerta": sum(1 for d in diagnosticos if "ALERTA" in d["estado"]),
            "aprobados": sum(1 for d in diagnosticos if d["estado"].startswith("APROBADO -"))
        },
        "casos": diagnosticos
    }

    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    print(f"\nReporte de auditoria guardado en: {ruta_salida}")


def main():
    # Rutas relativas al directorio raiz del proyecto
    ruta_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ruta_casos = os.path.join(ruta_base, "data", "casos.json")
    ruta_config = os.path.join(ruta_base, "config", "reglas.json")
    ruta_reporte = os.path.join(ruta_base, "output", "reporte_auditoria.json")

    print("=" * 60)
    print("AGENTE AUDITOR — Evaluacion de decisiones de Agent B")
    print("=" * 60)

    # Carga de insumos
    casos = cargar_json(ruta_casos)
    config = cargar_json(ruta_config)

    diagnosticos = []

    for caso in casos:
        # Capa 1: evaluacion determinista de reglas de negocio
        resultado_reglas = evaluar_reglas(caso, config)

        # Capa 2: evaluacion semantica de fidelidad
        resultado_fidelidad = evaluar_fidelidad(caso, resultado_reglas, config)

        # Consolidacion del diagnostico final
        diagnostico = construir_diagnostico(caso, resultado_reglas, resultado_fidelidad, config)
        diagnosticos.append(diagnostico)

        # Salida en consola con formato requerido por el reto
        imprimir_diagnostico(diagnostico)

    # Persistencia del reporte completo
    guardar_reporte(diagnosticos, ruta_reporte)

    print("\n" + "=" * 60)
    print("Evaluacion completada.")
    print("=" * 60)


if __name__ == "__main__":
    main()
