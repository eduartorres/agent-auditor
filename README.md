# Agente Auditor — AI Governance para Decisiones Autónomas

![CI](https://github.com/eduartorres/agent-auditor/actions/workflows/ci.yml/badge.svg)

Sistema de auditoría automatizada diseñado para evaluar las decisiones de un agente de IA
en tiempo real, garantizando el cumplimiento de reglas de negocio, límites normativos y
controles de riesgo antes de que impacten en producción.

---

## El Problema que Resuelve

Las compañías aseguradoras que despliegan agentes de IA autónomos para aprobar coberturas
y emitir pólizas enfrentan un riesgo operativo crítico: el agente puede tomar decisiones
incorrectas que violen límites de cobertura, ignoren alertas de cumplimiento regulatorio
o procesen cuentas bajo sospecha de abuso.

Este sistema actúa como una segunda línea de defensa automatizada que audita cada decisión
del agente antes o durante su impacto en producción.

---

## Arquitectura de la Solución

El auditor opera en dos capas complementarias:

**Capa 1 — Reglas Deterministas**
Evalúa las decisiones contra umbrales y restricciones de negocio definidos en un archivo
de configuración externo (`config/reglas.json`). Las violaciones en esta capa son binarias
e irrefutables: límites de cobertura excedidos, flags SARLAFT/AML, emisiones automáticas
fuera de rango.

**Capa 2 — Índice de Fidelidad Analítica**
Calcula la consistencia semántica entre el contexto normativo disponible para el agente
y la acción que tomó. Usa embeddings multilingües y similitud coseno para producir un
puntaje continuo entre 0.0 y 1.0. Un score bajo sin violación explícita es una señal
de alerta temprana.

El diagnóstico final integra ambas capas con prioridad clara: las violaciones deterministas
prevalecen siempre sobre el análisis semántico.

---

## Resultados sobre los Casos de Prueba

| Caso | Descripción | Estado | Índice de Fidelidad |
|------|-------------|--------|---------------------|
| 1 | Cobertura cristales $900 USD con deducible | APROBADO | ~0.85 |
| 2 | Cuenta sospechosa derivada a analista | APROBADO | ~0.80 |
| 3 | Póliza de vida $95,000 USD para asegurado de 62 años | RECHAZADO | ~0.15 |
| 4 | Emisión de póliza con alerta SARLAFT activa | BLOQUEADO | ~0.05 |

Los puntajes exactos se generan en cada ejecución y pueden consultarse en `output/reporte_auditoria.json`.

---

## Estructura del Proyecto

```
agent-auditor/
├── data/
│   └── casos.json              # Dataset de entrada con los logs de Agent B
├── config/
│   └── reglas.json             # Reglas de negocio, umbrales y palabras clave
├── src/
│   ├── auditor.py              # Orquestador principal — punto de entrada
│   ├── reglas_engine.py        # Capa determinista de evaluación
│   └── fidelidad.py            # Capa semántica — índice de fidelidad
├── output/
│   └── reporte_auditoria.json  # Generado en cada ejecución
├── .github/workflows/
│   └── ci.yml                  # Pipeline de validación continua
└── requirements.txt
```

---

## Cómo Ejecutar

**Requisitos:** Python 3.11+

```bash
# Clonar el repositorio
git clone https://github.com/<tu-usuario>/agent-auditor.git
cd agent-auditor

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar el auditor
cd src
python auditor.py
```

La primera ejecución descarga el modelo de embeddings (~120 MB). Las ejecuciones
siguientes usan la versión en caché local.

---

## Cómo Actualizar las Reglas de Negocio

Todas las reglas, umbrales y listas restrictivas están externalizadas en `config/reglas.json`.
Un analista de riesgos puede modificar límites de cobertura, agregar términos a listas SARLAFT
o ajustar umbrales de fidelidad sin intervención del equipo de desarrollo.

Cualquier cambio en el repositorio dispara automáticamente el pipeline de CI que valida
el comportamiento del auditor contra los casos de prueba.

---

## Escalabilidad en Producción

Para soportar miles de transacciones en tiempo real, la arquitectura escalaría sobre AWS:

- **Ingesta:** API Gateway + Lambda para recibir los logs de Agent B
- **Procesamiento:** ECS Fargate con el auditor containerizado, escalado horizontal automático
- **Embeddings:** SageMaker Endpoints para inferencia de alta disponibilidad
- **Persistencia:** S3 para reportes + DynamoDB para índices de auditoría consultables
- **Monitoreo:** CloudWatch para alertas en tiempo real sobre violaciones críticas
- **Gobierno:** Los reportes alimentan un dashboard en QuickSight para el Comité de Riesgos

Esta arquitectura desacopla la velocidad del agente de IA de la robustez del control,
garantizando latencia mínima en canal digital sin sacrificar gobierno.

---

## Decisiones de Diseño

**¿Por qué reglas externalizadas en JSON?**
Porque las reglas de negocio cambian con más frecuencia que el código. Separar configuración
de lógica es un principio de gobierno de IA — los cambios normativos no deben requerir
ciclos de desarrollo.

**¿Por qué similitud coseno sobre embeddings multilingües?**
Es interpretable, estable entre ejecuciones y no requiere datos de entrenamiento propios.
En un contexto de auditoría, la explicabilidad del método es tan importante como su precisión.

**¿Por qué penalizar el score semántico cuando hay violación determinista?**
Porque un agente puede repetir términos del contexto normativo en su respuesta y aun así
actuar en sentido contrario. El ajuste garantiza que el índice de fidelidad sea honesto
con respecto a la acción real, no solo a la similitud textual superficial.
