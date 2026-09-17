# Análisis de Criticidad de Activos

Herramienta interactiva para rankear activos por su impacto en producción y definir la estrategia de mantenimiento a partir de datos, no de intuición.

Basada en la metodología **Severidad × Ocurrencia** (alineada a ISO 55000): evalúa cada equipo en cuatro criterios con una escala no lineal, calcula un score de criticidad, asigna una prioridad operacional (P1–P4) y permite modelar un plan de acción (*reducer*).

## Criterios de evaluación

Cada criterio se evalúa en 5 niveles. La escala **no es lineal** — penaliza fuerte los casos extremos:

| Nivel | 1 | 2 | 3 | 4 | 5 |
|-------|---|---|---|---|---|
| Puntos | 1 | 4 | 7 | 10 | 20 |

1. **Obsolescencia de refacciones eléctricas** — % de partes obsoletas / sin soporte
2. **Impacto en capacidad de producción (PPR)** — % del volumen total que pasa por el equipo
3. **Posibilidad de redirigir producción** — qué tanto se puede mover el trabajo a otro equipo
4. **Paros significativos últimos 12 meses** — solo los que superaron el tiempo máximo permitido sin impacto

**Score de criticidad = Obsolescencia × Capacidad × Redirección × Paros**

El score es el **producto** de los cuatro factores. Como la escala por nivel no es lineal, un equipo en niveles altos en varios criterios escala de forma exponencial — así los casos verdaderamente críticos se separan del resto. El score crudo se normaliza a un **índice de criticidad 0–100%** para lectura rápida.

## Prioridad operacional (P1–P4)

La prioridad se define **solo** por el impacto en capacidad de producción y la posibilidad de redirigirla. Un equipo identificado como cuello de botella sube automáticamente a **P2 como mínimo**.

## Ejecutar en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

La app abre en `http://localhost:8501`.

## Desplegar en Streamlit Community Cloud

1. Sube este repositorio a GitHub.
2. Entra a [share.streamlit.io](https://share.streamlit.io) con tu cuenta de GitHub.
3. Crea una nueva app apuntando a este repo y al archivo `app.py`.

---

Desarrollada por Jesús Jaramillo — Sr. RMEP México.
