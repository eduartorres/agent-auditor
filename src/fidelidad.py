from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


# Módulo de fidelidad semántica del Agente Auditor.
# Calcula qué tan consistente es la respuesta de Agent B con el contexto
# normativo que tenía disponible al momento de tomar la decisión.
#
# La métrica central es la similitud coseno entre los embeddings del contexto
# y la respuesta. Un puntaje cercano a 1.0 indica alta coherencia semántica.
# Un puntaje bajo no implica necesariamente una violación, pero sí una señal
# de alerta que complementa el análisis de reglas deterministas.


# Se carga el modelo una sola vez al importar el módulo para evitar
# overhead en cada evaluación. El modelo multilingual cubre español sin problema.
_modelo = None


def _obtener_modelo() -> SentenceTransformer:
    """
    Carga el modelo de embeddings de forma lazy — solo cuando se necesita
    por primera vez. Esto evita tiempos de inicialización innecesarios
    si el módulo se importa pero no se usa en un flujo determinado.
    """
    global _modelo
    if _modelo is None:
        # paraphrase-multilingual-MiniLM-L12-v2 es ligero, rápido y
        # tiene buen desempeño en español sin necesidad de modelo dedicado
        _modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _modelo


def calcular_similitud_coseno(texto_a: str, texto_b: str) -> float:
    """
    Calcula la similitud coseno entre dos textos usando embeddings densos.
    Retorna un valor entre 0.0 y 1.0 donde:
      - 1.0 significa que ambos textos están perfectamente alineados
      - 0.0 significa que no tienen relación semántica detectable
    """
    modelo = _obtener_modelo()

    embeddings = modelo.encode([texto_a, texto_b])
    similitud = cosine_similarity([embeddings[0]], [embeddings[1]])

    return float(round(similitud[0][0], 4))


def ajustar_score_por_violacion(score_base: float, tiene_violacion: bool, severidad: str) -> float:
    """
    Ajusta el índice semántico base cuando el motor de reglas ya detectó
    una violación determinista. El ajuste penaliza el score proporcionalmente
    a la severidad de la violación encontrada.

    Esto garantiza que casos con violaciones claras nunca obtengan un
    índice de fidelidad alto por coincidencia semántica superficial.
    Por ejemplo: el caso 4 puede tener similitud textual alta porque
    el agente repite términos del contexto, pero la acción es contraria
    a la instrucción — el ajuste corrige esa distorsión.
    """
    if not tiene_violacion:
        return score_base

    penalizaciones = {
        "CRITICA": 0.85,
        "ALTA":    0.65,
        "MEDIA":   0.35,
        "NINGUNA": 0.0
    }

    penalizacion = penalizaciones.get(severidad, 0.0)
    score_ajustado = max(0.0, score_base - penalizacion)

    return float(round(score_ajustado, 4))


def interpretar_score(score: float, config: dict) -> str:
    """
    Convierte el score numérico en una interpretación legible para el negocio.
    Usa los umbrales definidos en reglas.json para mantener consistencia
    entre la configuración y el diagnóstico generado.
    """
    umbral_minimo = config["umbrales_fidelidad"]["score_minimo_aceptable"]
    umbral_alerta = config["umbrales_fidelidad"]["score_alerta"]

    if score >= umbral_minimo:
        return "Alta consistencia semántica entre contexto normativo y acción del agente"
    elif score >= umbral_alerta:
        return "Consistencia semántica moderada — se recomienda revisión"
    else:
        return "Baja consistencia semántica — la acción del agente diverge del contexto normativo"


def evaluar_fidelidad(caso: dict, resultado_reglas: dict, config: dict) -> dict:
    """
    Punto de entrada principal del módulo semántico.
    Recibe el caso y el resultado previo del motor de reglas,
    calcula el índice de fidelidad y retorna el diagnóstico completo.

    El score final integra tanto la similitud semántica como las
    penalizaciones por violaciones deterministas ya detectadas.
    """
    contexto = caso["contexto_rag"]
    respuesta = caso["respuesta_agent_b"]

    tiene_violacion = resultado_reglas["tiene_violacion"]
    severidad = resultado_reglas["severidad"]

    # Calcula la similitud semántica base entre contexto y respuesta
    score_base = calcular_similitud_coseno(contexto, respuesta)

    # Ajusta el score si el motor de reglas detectó una violación
    score_final = ajustar_score_por_violacion(score_base, tiene_violacion, severidad)

    interpretacion = interpretar_score(score_final, config)

    return {
        "score_base": score_base,
        "score_final": score_final,
        "interpretacion": interpretacion
    }
