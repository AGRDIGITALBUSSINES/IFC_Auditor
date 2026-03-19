# ⬡ IFC Auditor

**Analizador y optimizador de modelos BIM en formato IFC.**

Herramienta de escritorio desarrollada en Python que permite auditar archivos IFC (Industry Foundation Classes), identificar problemas de calidad y optimizar modelos eliminando entidades innecesarias.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/Licencia-MIT-green)
![Platform](https://img.shields.io/badge/Plataforma-Windows%20|%20Linux%20|%20macOS-blue)
![Visitas](https://visitor-badge.laobi.icu/badge?page_id=AGRDIGITALBUSSINES.IFC_Auditor)

---

## Características

### Auditoría completa
- **Inventario de entidades** — Conteo y clasificación de todas las entidades IFC del modelo.
- **Análisis de PropertySets** — Detección de PropertySets vacíos y nombres duplicados.
- **Elementos huérfanos** — Identificación de elementos sin contenedor espacial (muros, losas, columnas, vigas, puertas, ventanas, etc.).
- **Tipos sin instancias** — Detección de `IfcTypeObject` definidos pero no utilizados en el modelo.
- **Análisis de geometría** — Clasificación de representaciones geométricas (SweptSolid, BRep, Clipping, etc.) con alertas sobre geometrías pesadas.

### Optimización
- Eliminación de PropertySets vacíos.
- Eliminación de tipos sin instancias.
- Generación de archivo IFC optimizado con reporte de reducción de tamaño.

### Exportación
- Reporte de auditoría en formato **JSON**.

### Interfaz gráfica
- UI moderna con tema oscuro construida con Tkinter.
- Pestañas organizadas: Resumen, Inventario, Problemas y Optimizar.
- KPIs visuales: tamaño del archivo, total de entidades, problemas detectados y schema IFC.
- Análisis en hilo secundario (no bloquea la interfaz).

---

## Requisitos

- **Python 3.8** o superior
- Dependencias:

```
ifcopenshell
pandas
```

## Instalación

1. Clona el repositorio:

```bash
git clone https://github.com/AGRDIGITALBUSSINES/IFC_Auditor.git
cd IFC_Auditor
```

2. Instala las dependencias:

```bash
pip install ifcopenshell pandas
```

3. Ejecuta la aplicación:

```bash
python ifc_auditor.py
```

---

## Uso

1. Abre la aplicación y selecciona un archivo `.ifc` con el botón **Examinar**.
2. Presiona **▶ Analizar** para ejecutar la auditoría.
3. Revisa los resultados en las pestañas:
   - **📊 Resumen** — Vista general con KPIs y diagnóstico detallado.
   - **📋 Inventario** — Tabla con todas las entidades del modelo ordenadas por cantidad.
   - **⚠️ Problemas** — PropertySets vacíos/duplicados, elementos huérfanos, tipos sin uso y análisis de geometría.
   - **🔧 Optimizar** — Selecciona opciones de limpieza, genera un IFC optimizado o exporta el reporte en JSON.

---

## Estructura del proyecto

```
IFC_Auditor/
├── ifc_auditor.py    # Código principal (lógica de auditoría + interfaz gráfica)
├── .gitignore
└── README.md
```

---

## Tecnologías

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3 |
| Parsing IFC | [IfcOpenShell](https://ifcopenshell.org/) |
| Datos | Pandas |
| Interfaz | Tkinter |

---

## Desarrollado por

**[AGR Digital Business](https://agrdb.com)** — Soluciones digitales para la industria AEC/BIM.
