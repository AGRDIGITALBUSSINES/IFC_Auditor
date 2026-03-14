"""
IFC Auditor - Analizador y optimizador de modelos IFC
Requiere: pip install ifcopenshell pandas
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import json
import webbrowser
from collections import Counter
from datetime import datetime

# ──────────────────────────────────────────────
#  INTENTO DE IMPORTAR DEPENDENCIAS OPCIONALES
# ──────────────────────────────────────────────
try:
    import ifcopenshell
    import ifcopenshell.util.element as util
    IFC_AVAILABLE = True
except Exception:
    IFC_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


# ══════════════════════════════════════════════
#  LÓGICA DE AUDITORÍA (independiente de la UI)
# ══════════════════════════════════════════════

class IFCAuditor:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.model = None
        self.resultados = {}

    def cargar(self):
        self.model = ifcopenshell.open(self.filepath)
        self.file_size_mb = os.path.getsize(self.filepath) / (1024 * 1024)

    # ── 1. Inventario general ──────────────────
    def inventario_tipos(self) -> dict:
        conteo = Counter(e.is_a() for e in self.model)
        return dict(sorted(conteo.items(), key=lambda x: x[1], reverse=True))

    # ── 2. Análisis de PropertySets ───────────
    def analizar_psets(self) -> dict:
        todos = self.model.by_type("IfcPropertySet")
        vacios = [p for p in todos if not p.HasProperties]
        nombres = Counter(p.Name for p in todos if p.Name)
        dup_nombres = {n: c for n, c in nombres.items() if c > 1}

        return {
            "total_psets": len(todos),
            "psets_vacios": len(vacios),
            "ids_vacios": [p.id() for p in vacios],
            "nombres_duplicados": dup_nombres,
            "total_duplicados": sum(v - 1 for v in dup_nombres.values()),
        }

    # ── 3. Elementos huérfanos ─────────────────
    def elementos_huerfanos(self) -> list:
        huerfanos = []
        tipos_espaciales = [
            "IfcWall", "IfcSlab", "IfcBeam", "IfcColumn",
            "IfcDoor", "IfcWindow", "IfcStair", "IfcRoof",
            "IfcFurnishingElement", "IfcBuildingElementProxy"
        ]
        for tipo in tipos_espaciales:
            for elem in self.model.by_type(tipo):
                if not util.get_container(elem):
                    huerfanos.append({
                        "id": elem.id(),
                        "tipo": elem.is_a(),
                        "nombre": getattr(elem, "Name", "Sin nombre") or "Sin nombre",
                    })
        return huerfanos

    # ── 4. Tipos sin instancias ────────────────
    def tipos_sin_instancias(self) -> list:
        tipos_definidos = self.model.by_type("IfcTypeObject")
        sin_uso = []
        for tipo in tipos_definidos:
            if hasattr(tipo, "ObjectTypeOf") and not tipo.ObjectTypeOf:
                sin_uso.append({
                    "id": tipo.id(),
                    "tipo": tipo.is_a(),
                    "nombre": getattr(tipo, "Name", "Sin nombre") or "Sin nombre",
                })
        return sin_uso

    # ── 5. Análisis de geometría ───────────────
    def analizar_geometria(self) -> dict:
        rep_types = Counter()
        for rep in self.model.by_type("IfcShapeRepresentation"):
            if rep.RepresentationType:
                rep_types[rep.RepresentationType] += 1

        breps = rep_types.get("Brep", 0) + rep_types.get("SurfaceModel", 0)
        extrusions = rep_types.get("SweptSolid", 0) + rep_types.get("Clipping", 0)
        return {
            "tipos_representacion": dict(rep_types),
            "breps_complejos": breps,
            "extrusions_eficientes": extrusions,
            "alerta_brep": breps > extrusions and breps > 10,
        }

    # ── 6. Resumen ejecutivo ───────────────────
    def resumen(self) -> dict:
        inv = self.inventario_tipos()
        psets = self.analizar_psets()
        huerfanos = self.elementos_huerfanos()
        sin_inst = self.tipos_sin_instancias()
        geo = self.analizar_geometria()

        total_entidades = sum(inv.values())
        potencial_limpieza = (
            psets["psets_vacios"]
            + psets["total_duplicados"]
            + len(sin_inst)
        )

        return {
            "archivo": os.path.basename(self.filepath),
            "tamano_mb": round(self.file_size_mb, 2),
            "schema": self.model.schema,
            "total_entidades": total_entidades,
            "inventario": inv,
            "psets": psets,
            "huerfanos": huerfanos,
            "tipos_sin_instancias": sin_inst,
            "geometria": geo,
            "potencial_limpieza": potencial_limpieza,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    # ── 7. Optimización ───────────────────────
    def optimizar(self, output_path: str, opciones: dict) -> dict:
        eliminados = 0

        if opciones.get("psets_vacios"):
            vacios = [
                self.model.by_id(i)
                for i in self.resultados["psets"]["ids_vacios"]
                if self.model.by_id(i)
            ]
            for p in vacios:
                self.model.remove(p)
            eliminados += len(vacios)

        if opciones.get("tipos_sin_instancias"):
            for item in self.resultados["tipos_sin_instancias"]:
                try:
                    ent = self.model.by_id(item["id"])
                    if ent:
                        self.model.remove(ent)
                        eliminados += 1
                except Exception:
                    pass

        self.model.write(output_path)
        nuevo_size = os.path.getsize(output_path) / (1024 * 1024)
        reduccion = self.file_size_mb - nuevo_size

        return {
            "eliminados": eliminados,
            "tamano_original_mb": round(self.file_size_mb, 2),
            "tamano_nuevo_mb": round(nuevo_size, 2),
            "reduccion_mb": round(reduccion, 2),
            "reduccion_pct": round((reduccion / self.file_size_mb) * 100, 1) if self.file_size_mb else 0,
        }

    def ejecutar_auditoria(self) -> dict:
        self.cargar()
        self.resultados = self.resumen()
        return self.resultados


# ══════════════════════════════════════════════
#  INTERFAZ TKINTER
# ══════════════════════════════════════════════

COLORES = {
    "bg_oscuro":   "#1a1d23",
    "bg_panel":    "#22262f",
    "bg_tarjeta":  "#2a2f3a",
    "acento":      "#4f8ef7",
    "acento2":     "#38c98e",
    "alerta":      "#f0a04b",
    "error":       "#e05c5c",
    "texto":       "#e8eaf0",
    "texto_dim":   "#8891a8",
    "borde":       "#353c4a",
}

FUENTE_TITULO  = ("Segoe UI", 13, "bold")
FUENTE_NORMAL  = ("Segoe UI", 10)
FUENTE_PEQUEÑA = ("Segoe UI", 9)
FUENTE_MONO    = ("Consolas", 9)
FUENTE_KPI     = ("Segoe UI", 22, "bold")


class IFCAuditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IFC Auditor — Analizador de Modelos BIM | AGRDB")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(bg=COLORES["bg_oscuro"])
        self.resizable(True, True)

        self.filepath = tk.StringVar()
        self.auditor = None
        self.resultados = None

        # Opciones de optimización
        self.opt_psets_vacios    = tk.BooleanVar(value=True)
        self.opt_tipos_sin_inst  = tk.BooleanVar(value=True)

        self._construir_ui()
        self._check_dependencias()

    # ── Verificación de dependencias ──────────
    def _check_dependencias(self):
        faltantes = []
        if not IFC_AVAILABLE:
            faltantes.append("ifcopenshell")
        if not PANDAS_AVAILABLE:
            faltantes.append("pandas")
        if faltantes:
            messagebox.showwarning(
                "Dependencias faltantes",
                f"Instala los siguientes paquetes para usar todas las funciones:\n\n"
                f"  pip install {' '.join(faltantes)}\n\n"
                f"La interfaz se mostrará pero el análisis no funcionará."
            )

    # ── Construcción de UI ────────────────────
    def _construir_ui(self):
        # Header
        header = tk.Frame(self, bg=COLORES["bg_panel"], height=56)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(
            header, text="⬡  IFC AUDITOR",
            font=("Segoe UI", 14, "bold"),
            fg=COLORES["acento"], bg=COLORES["bg_panel"]
        ).pack(side="left", padx=20, pady=14)

        tk.Label(
            header, text="Análisis y optimización de modelos BIM",
            font=FUENTE_PEQUEÑA,
            fg=COLORES["texto_dim"], bg=COLORES["bg_panel"]
        ).pack(side="left", padx=4, pady=14)

        # Branding AGRDB
        brand_frame = tk.Frame(header, bg=COLORES["bg_panel"])
        brand_frame.pack(side="right", padx=20, pady=14)
        tk.Label(
            brand_frame, text="Desarrollado por",
            font=FUENTE_PEQUEÑA,
            fg=COLORES["texto_dim"], bg=COLORES["bg_panel"]
        ).pack(side="left")
        brand_link = tk.Label(
            brand_frame, text=" AGRDB",
            font=("Segoe UI", 10, "bold"),
            fg=COLORES["acento"], bg=COLORES["bg_panel"],
            cursor="hand2"
        )
        brand_link.pack(side="left")
        brand_link.bind("<Button-1>", lambda e: webbrowser.open("https://agrdb.com"))
        brand_link.bind("<Enter>", lambda e: brand_link.config(fg=COLORES["acento2"]))
        brand_link.bind("<Leave>", lambda e: brand_link.config(fg=COLORES["acento"]))

        # Barra de archivo
        self._barra_archivo()

        # Contenido principal con pestañas
        self.notebook = ttk.Notebook(self)
        self._estilo_notebook()
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        self.tab_resumen    = tk.Frame(self.notebook, bg=COLORES["bg_oscuro"])
        self.tab_inventario = tk.Frame(self.notebook, bg=COLORES["bg_oscuro"])
        self.tab_problemas  = tk.Frame(self.notebook, bg=COLORES["bg_oscuro"])
        self.tab_optimizar  = tk.Frame(self.notebook, bg=COLORES["bg_oscuro"])

        self.notebook.add(self.tab_resumen,    text="  📊 Resumen  ")
        self.notebook.add(self.tab_inventario, text="  📋 Inventario  ")
        self.notebook.add(self.tab_problemas,  text="  ⚠️  Problemas  ")
        self.notebook.add(self.tab_optimizar,  text="  🔧 Optimizar  ")

        self._construir_tab_resumen()
        self._construir_tab_inventario()
        self._construir_tab_problemas()
        self._construir_tab_optimizar()

        # Barra de estado
        self.status_var = tk.StringVar(value="Selecciona un archivo IFC para comenzar")
        barra_estado = tk.Frame(self, bg=COLORES["bg_panel"], height=28)
        barra_estado.pack(fill="x", side="bottom")
        barra_estado.pack_propagate(False)
        tk.Label(
            barra_estado, textvariable=self.status_var,
            font=FUENTE_PEQUEÑA, fg=COLORES["texto_dim"],
            bg=COLORES["bg_panel"], anchor="w"
        ).pack(side="left", padx=12, pady=4)

        footer_link = tk.Label(
            barra_estado, text="agrdb.com",
            font=("Segoe UI", 9, "bold"),
            fg=COLORES["acento"], bg=COLORES["bg_panel"],
            cursor="hand2"
        )
        footer_link.pack(side="right", padx=12, pady=4)
        footer_link.bind("<Button-1>", lambda e: webbrowser.open("https://agrdb.com"))
        footer_link.bind("<Enter>", lambda e: footer_link.config(fg=COLORES["acento2"]))
        footer_link.bind("<Leave>", lambda e: footer_link.config(fg=COLORES["acento"]))
        tk.Label(
            barra_estado, text="⬡",
            font=FUENTE_PEQUEÑA, fg=COLORES["texto_dim"],
            bg=COLORES["bg_panel"]
        ).pack(side="right")

    def _barra_archivo(self):
        frame = tk.Frame(self, bg=COLORES["bg_panel"], pady=10)
        frame.pack(fill="x", padx=12, pady=(8, 0))

        tk.Label(
            frame, text="Archivo IFC:",
            font=FUENTE_NORMAL, fg=COLORES["texto_dim"],
            bg=COLORES["bg_panel"]
        ).pack(side="left", padx=(4, 6))

        entry = tk.Entry(
            frame, textvariable=self.filepath,
            font=FUENTE_MONO, fg=COLORES["texto"],
            bg=COLORES["bg_tarjeta"], relief="flat",
            insertbackground=COLORES["acento"],
            width=55
        )
        entry.pack(side="left", ipady=5, padx=(0, 8))

        self._btn(frame, "Examinar", self._seleccionar_archivo,
                  color=COLORES["texto_dim"]).pack(side="left", padx=4)
        self._btn(frame, "▶  Analizar", self._iniciar_analisis,
                  color=COLORES["acento"]).pack(side="left", padx=4)

        self.progress = ttk.Progressbar(
            frame, mode="indeterminate", length=120
        )
        self.progress.pack(side="left", padx=8)

    # ── Tab Resumen ───────────────────────────
    def _construir_tab_resumen(self):
        p = self.tab_resumen

        # KPIs row
        self.kpi_frame = tk.Frame(p, bg=COLORES["bg_oscuro"])
        self.kpi_frame.pack(fill="x", pady=(16, 8), padx=16)

        self.kpis = {}
        kpi_defs = [
            ("tamano",    "Tamaño",      "— MB",  COLORES["acento"]),
            ("entidades", "Entidades",   "—",     COLORES["acento2"]),
            ("problemas", "Problemas",   "—",     COLORES["alerta"]),
            ("schema",    "Schema IFC",  "—",     COLORES["texto_dim"]),
        ]
        for key, label, default, color in kpi_defs:
            card = tk.Frame(self.kpi_frame, bg=COLORES["bg_tarjeta"],
                            relief="flat", bd=0)
            card.pack(side="left", expand=True, fill="both", padx=6, pady=4, ipadx=12, ipady=10)

            val_lbl = tk.Label(card, text=default, font=FUENTE_KPI,
                               fg=color, bg=COLORES["bg_tarjeta"])
            val_lbl.pack()
            tk.Label(card, text=label, font=FUENTE_PEQUEÑA,
                     fg=COLORES["texto_dim"], bg=COLORES["bg_tarjeta"]).pack()
            self.kpis[key] = val_lbl

        # Área de texto resumen
        frame_texto = tk.Frame(p, bg=COLORES["bg_oscuro"])
        frame_texto.pack(fill="both", expand=True, padx=16, pady=8)

        tk.Label(frame_texto, text="Diagnóstico detallado",
                 font=FUENTE_TITULO, fg=COLORES["texto"],
                 bg=COLORES["bg_oscuro"]).pack(anchor="w", pady=(0, 6))

        self.txt_resumen = self._text_area(frame_texto)
        self.txt_resumen.pack(fill="both", expand=True)
        self._escribir(self.txt_resumen,
                       "Abre un archivo IFC y presiona ▶ Analizar para comenzar.\n")

    # ── Tab Inventario ────────────────────────
    def _construir_tab_inventario(self):
        p = self.tab_inventario

        tk.Label(p, text="Inventario de entidades por tipo",
                 font=FUENTE_TITULO, fg=COLORES["texto"],
                 bg=COLORES["bg_oscuro"]).pack(anchor="w", padx=16, pady=(14, 6))

        # Tabla
        frame_tabla = tk.Frame(p, bg=COLORES["bg_oscuro"])
        frame_tabla.pack(fill="both", expand=True, padx=16, pady=8)

        cols = ("Tipo IFC", "Cantidad", "% del total")
        self.tree_inv = self._crear_treeview(frame_tabla, cols)
        self.tree_inv.pack(fill="both", expand=True)

    # ── Tab Problemas ─────────────────────────
    def _construir_tab_problemas(self):
        p = self.tab_problemas

        # Sub-tabs con pestañas internas
        nb2 = ttk.Notebook(p)
        nb2.pack(fill="both", expand=True, padx=12, pady=12)

        self.tab_psets    = tk.Frame(nb2, bg=COLORES["bg_oscuro"])
        self.tab_huerfanos = tk.Frame(nb2, bg=COLORES["bg_oscuro"])
        self.tab_tipos    = tk.Frame(nb2, bg=COLORES["bg_oscuro"])
        self.tab_geo      = tk.Frame(nb2, bg=COLORES["bg_oscuro"])

        nb2.add(self.tab_psets,     text="  PropertySets  ")
        nb2.add(self.tab_huerfanos, text="  Huérfanos  ")
        nb2.add(self.tab_tipos,     text="  Tipos sin uso  ")
        nb2.add(self.tab_geo,       text="  Geometría  ")

        # Psets
        tk.Label(self.tab_psets, text="PropertySets vacíos y duplicados",
                 font=FUENTE_TITULO, fg=COLORES["texto"],
                 bg=COLORES["bg_oscuro"]).pack(anchor="w", padx=12, pady=(12, 4))
        self.txt_psets = self._text_area(self.tab_psets)
        self.txt_psets.pack(fill="both", expand=True, padx=12, pady=8)

        # Huérfanos
        tk.Label(self.tab_huerfanos, text="Elementos sin contenedor espacial",
                 font=FUENTE_TITULO, fg=COLORES["texto"],
                 bg=COLORES["bg_oscuro"]).pack(anchor="w", padx=12, pady=(12, 4))
        cols_h = ("ID", "Tipo", "Nombre")
        self.tree_huerfanos = self._crear_treeview(self.tab_huerfanos, cols_h)
        self.tree_huerfanos.pack(fill="both", expand=True, padx=12, pady=8)

        # Tipos sin instancias
        tk.Label(self.tab_tipos, text="Tipos definidos sin instancias en el modelo",
                 font=FUENTE_TITULO, fg=COLORES["texto"],
                 bg=COLORES["bg_oscuro"]).pack(anchor="w", padx=12, pady=(12, 4))
        cols_t = ("ID", "Tipo IFC", "Nombre")
        self.tree_tipos = self._crear_treeview(self.tab_tipos, cols_t)
        self.tree_tipos.pack(fill="both", expand=True, padx=12, pady=8)

        # Geometría
        tk.Label(self.tab_geo, text="Análisis de representaciones geométricas",
                 font=FUENTE_TITULO, fg=COLORES["texto"],
                 bg=COLORES["bg_oscuro"]).pack(anchor="w", padx=12, pady=(12, 4))
        self.txt_geo = self._text_area(self.tab_geo)
        self.txt_geo.pack(fill="both", expand=True, padx=12, pady=8)

    # ── Tab Optimizar ─────────────────────────
    def _construir_tab_optimizar(self):
        p = self.tab_optimizar

        tk.Label(p, text="Opciones de optimización",
                 font=FUENTE_TITULO, fg=COLORES["texto"],
                 bg=COLORES["bg_oscuro"]).pack(anchor="w", padx=16, pady=(16, 8))

        # Opciones checkboxes
        frame_opts = tk.Frame(p, bg=COLORES["bg_tarjeta"])
        frame_opts.pack(fill="x", padx=16, pady=4, ipadx=10, ipady=10)

        opciones = [
            (self.opt_psets_vacios,   "Eliminar PropertySets vacíos",
             "Remueve IfcPropertySet sin propiedades asociadas"),
            (self.opt_tipos_sin_inst, "Eliminar tipos sin instancias",
             "Remueve IfcTypeObject que no tienen elementos que los usen"),
        ]

        for var, titulo, desc in opciones:
            row = tk.Frame(frame_opts, bg=COLORES["bg_tarjeta"])
            row.pack(fill="x", pady=4)
            tk.Checkbutton(
                row, variable=var, text=titulo,
                font=FUENTE_NORMAL, fg=COLORES["texto"],
                bg=COLORES["bg_tarjeta"], activebackground=COLORES["bg_tarjeta"],
                selectcolor=COLORES["bg_oscuro"],
                activeforeground=COLORES["acento"]
            ).pack(side="left")
            tk.Label(row, text=f"  — {desc}", font=FUENTE_PEQUEÑA,
                     fg=COLORES["texto_dim"], bg=COLORES["bg_tarjeta"]).pack(side="left")

        # Botón optimizar
        btn_frame = tk.Frame(p, bg=COLORES["bg_oscuro"])
        btn_frame.pack(fill="x", padx=16, pady=12)
        self._btn(btn_frame, "💾  Optimizar y guardar IFC", self._optimizar,
                  color=COLORES["acento2"]).pack(side="left")
        self._btn(btn_frame, "📄  Exportar reporte JSON", self._exportar_json,
                  color=COLORES["texto_dim"]).pack(side="left", padx=8)

        # Log de optimización
        tk.Label(p, text="Log de optimización",
                 font=FUENTE_TITULO, fg=COLORES["texto"],
                 bg=COLORES["bg_oscuro"]).pack(anchor="w", padx=16, pady=(8, 4))
        self.txt_opt = self._text_area(p, height=10)
        self.txt_opt.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self._escribir(self.txt_opt,
                       "Ejecuta el análisis primero, luego usa los botones de arriba.\n")

    # ── Acciones ──────────────────────────────
    def _seleccionar_archivo(self):
        path = filedialog.askopenfilename(
            title="Seleccionar archivo IFC",
            filetypes=[("IFC files", "*.ifc"), ("Todos", "*.*")]
        )
        if path:
            self.filepath.set(path)

    def _iniciar_analisis(self):
        if not IFC_AVAILABLE:
            messagebox.showerror("Error", "ifcopenshell no está instalado.\n\npip install ifcopenshell")
            return

        path = self.filepath.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning("Archivo no válido",
                                   "Selecciona un archivo IFC existente.")
            return

        self.progress.start(10)
        self.status_var.set("Analizando modelo… por favor espera")
        threading.Thread(target=self._ejecutar_analisis, args=(path,),
                         daemon=True).start()

    def _ejecutar_analisis(self, path):
        try:
            self.auditor = IFCAuditor(path)
            self.resultados = self.auditor.ejecutar_auditoria()
            self.after(0, self._mostrar_resultados)
        except Exception as e:
            self.after(0, lambda: self._error_analisis(str(e)))

    def _error_analisis(self, msg):
        self.progress.stop()
        self.status_var.set(f"Error: {msg}")
        messagebox.showerror("Error al analizar", msg)

    def _mostrar_resultados(self):
        self.progress.stop()
        r = self.resultados

        # ── KPIs
        self.kpis["tamano"].config(text=f"{r['tamano_mb']} MB")
        self.kpis["entidades"].config(text=f"{r['total_entidades']:,}")
        self.kpis["problemas"].config(text=str(r["potencial_limpieza"]))
        self.kpis["schema"].config(text=r["schema"])

        # ── Resumen texto
        self.txt_resumen.config(state="normal")
        self.txt_resumen.delete("1.0", "end")
        lineas = [
            f"📁  Archivo:        {r['archivo']}",
            f"📐  Schema:         {r['schema']}",
            f"💾  Tamaño:         {r['tamano_mb']} MB",
            f"🔢  Total entidades:{r['total_entidades']:,}",
            f"📅  Analizado:      {r['timestamp']}",
            "",
            "── DIAGNÓSTICO ─────────────────────────────────────",
            f"  PropertySets vacíos:       {r['psets']['psets_vacios']}",
            f"  Nombres duplicados en PSets:{r['psets']['total_duplicados']}",
            f"  Elementos huérfanos:       {len(r['huerfanos'])}",
            f"  Tipos sin instancias:      {len(r['tipos_sin_instancias'])}",
            f"  BReps complejos detectados:{r['geometria']['breps_complejos']}",
            "",
            f"  ✦ Entidades candidatas a eliminación: {r['potencial_limpieza']}",
        ]
        if r["geometria"]["alerta_brep"]:
            lineas.append("\n  ⚠  El modelo contiene muchas geometrías BRep.")
            lineas.append("     Considera reemplazarlas por SweptSolid en origen (Revit/Archicad).")
        self.txt_resumen.insert("end", "\n".join(lineas))
        self.txt_resumen.config(state="disabled")

        # ── Inventario
        for item in self.tree_inv.get_children():
            self.tree_inv.delete(item)
        total = r["total_entidades"]
        for i, (tipo, cant) in enumerate(r["inventario"].items()):
            pct = f"{cant/total*100:.1f}%" if total else "—"
            tag = "par" if i % 2 == 0 else "impar"
            self.tree_inv.insert("", "end", values=(tipo, f"{cant:,}", pct), tags=(tag,))

        # ── Psets
        p = r["psets"]
        self._escribir(self.txt_psets,
            f"Total PropertySets:          {p['total_psets']}\n"
            f"PropertySets vacíos:         {p['psets_vacios']}\n"
            f"Nombres duplicados:          {len(p['nombres_duplicados'])}\n"
            f"Instancias duplicadas totales:{p['total_duplicados']}\n\n"
            + ("── Top nombres duplicados ──────────────────\n"
               + "\n".join(f"  {n}: {c} veces" for n, c in
                           list(p["nombres_duplicados"].items())[:20])
               if p["nombres_duplicados"] else "  No se encontraron nombres duplicados.")
        )

        # ── Huérfanos
        for item in self.tree_huerfanos.get_children():
            self.tree_huerfanos.delete(item)
        for i, h in enumerate(r["huerfanos"]):
            tag = "par" if i % 2 == 0 else "impar"
            self.tree_huerfanos.insert(
                "", "end", values=(h["id"], h["tipo"], h["nombre"]), tags=(tag,))

        # ── Tipos sin instancias
        for item in self.tree_tipos.get_children():
            self.tree_tipos.delete(item)
        for i, t in enumerate(r["tipos_sin_instancias"]):
            tag = "par" if i % 2 == 0 else "impar"
            self.tree_tipos.insert(
                "", "end", values=(t["id"], t["tipo"], t["nombre"]), tags=(tag,))

        # ── Geometría
        geo = r["geometria"]
        lineas_geo = ["Tipos de representación encontrados:\n"]
        for tipo, cant in sorted(geo["tipos_representacion"].items(),
                                  key=lambda x: x[1], reverse=True):
            barra = "█" * min(cant // 5 + 1, 30)
            lineas_geo.append(f"  {tipo:<25} {cant:>5}  {barra}")
        if geo["alerta_brep"]:
            lineas_geo.append(
                "\n⚠  ALERTA: El modelo tiene más BReps que SweptSolids.\n"
                "   Los BReps son geometría explícita (pesada) generada por exportadores.\n"
                "   Origen probable: Revit exportado sin configuración IFC optimizada."
            )
        self._escribir(self.txt_geo, "\n".join(lineas_geo))

        self.status_var.set(
            f"✔  Análisis completado — {r['total_entidades']:,} entidades | "
            f"{r['potencial_limpieza']} candidatos a limpiar"
        )

    def _optimizar(self):
        if not self.resultados:
            messagebox.showwarning("Sin datos", "Ejecuta el análisis primero.")
            return

        output = filedialog.asksaveasfilename(
            title="Guardar IFC optimizado",
            defaultextension=".ifc",
            filetypes=[("IFC files", "*.ifc")],
            initialfile="modelo_optimizado.ifc"
        )
        if not output:
            return

        opciones = {
            "psets_vacios":       self.opt_psets_vacios.get(),
            "tipos_sin_instancias": self.opt_tipos_sin_inst.get(),
        }

        self.status_var.set("Optimizando modelo…")
        self.progress.start(10)

        def _run():
            try:
                stats = self.auditor.optimizar(output, opciones)
                self.after(0, lambda: self._mostrar_opt_resultado(stats, output))
            except Exception as e:
                self.after(0, lambda: self._error_analisis(str(e)))

        threading.Thread(target=_run, daemon=True).start()

    def _mostrar_opt_resultado(self, stats, output):
        self.progress.stop()
        self._escribir(self.txt_opt,
            f"✔  Optimización completada\n"
            f"   Entidades eliminadas:  {stats['eliminados']}\n"
            f"   Tamaño original:       {stats['tamano_original_mb']} MB\n"
            f"   Tamaño nuevo:          {stats['tamano_nuevo_mb']} MB\n"
            f"   Reducción:             {stats['reduccion_mb']} MB "
            f"({stats['reduccion_pct']}%)\n"
            f"   Guardado en: {output}\n"
            f"{'─'*50}\n"
        )
        self.status_var.set(
            f"✔  Modelo guardado — reducción de {stats['reduccion_pct']}%"
        )

    def _exportar_json(self):
        if not self.resultados:
            messagebox.showwarning("Sin datos", "Ejecuta el análisis primero.")
            return

        output = filedialog.asksaveasfilename(
            title="Guardar reporte JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="reporte_ifc.json"
        )
        if not output:
            return

        # Serializar (limpiar objetos no serializables)
        def limpiar(obj):
            if isinstance(obj, dict):
                return {k: limpiar(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [limpiar(i) for i in obj]
            if isinstance(obj, (int, float, str, bool)) or obj is None:
                return obj
            return str(obj)

        with open(output, "w", encoding="utf-8") as f:
            json.dump(limpiar(self.resultados), f, indent=2, ensure_ascii=False)

        self.status_var.set(f"✔  Reporte exportado: {os.path.basename(output)}")
        self._escribir(self.txt_opt, f"📄  Reporte JSON guardado: {output}\n")

    # ── Helpers de UI ─────────────────────────
    def _btn(self, parent, texto, comando, color=None):
        color = color or COLORES["acento"]
        b = tk.Button(
            parent, text=texto, command=comando,
            font=FUENTE_NORMAL,
            fg=color, bg=COLORES["bg_tarjeta"],
            activeforeground="white",
            activebackground=COLORES["borde"],
            relief="flat", cursor="hand2",
            padx=14, pady=6, bd=0
        )
        b.bind("<Enter>", lambda e: b.config(bg=COLORES["borde"]))
        b.bind("<Leave>", lambda e: b.config(bg=COLORES["bg_tarjeta"]))
        return b

    def _text_area(self, parent, height=None):
        frame = tk.Frame(parent, bg=COLORES["borde"], bd=1)
        frame.pack_propagate(True)
        kw = dict(
            font=FUENTE_MONO,
            fg=COLORES["texto"], bg=COLORES["bg_tarjeta"],
            insertbackground=COLORES["acento"],
            relief="flat", wrap="word",
            state="disabled", padx=10, pady=8,
            selectbackground=COLORES["acento"],
        )
        if height:
            kw["height"] = height
        txt = tk.Text(frame, **kw)
        sb = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        # Guardar referencia al frame contenedor para poder hacer pack
        txt._frame = frame
        # Override pack para empaquetar el frame
        def _pack_frame(*args, **kwargs):
            frame.pack(*args, **kwargs)
        txt.pack = _pack_frame
        return txt

    def _escribir(self, widget, texto):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", texto)
        widget.config(state="disabled")

    def _crear_treeview(self, parent, columnas):
        frame = tk.Frame(parent, bg=COLORES["bg_oscuro"])
        frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.Treeview",
            background=COLORES["bg_tarjeta"],
            foreground=COLORES["texto"],
            fieldbackground=COLORES["bg_tarjeta"],
            rowheight=24,
            font=FUENTE_PEQUEÑA,
        )
        style.configure("Custom.Treeview.Heading",
            background=COLORES["bg_panel"],
            foreground=COLORES["acento"],
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )
        style.map("Custom.Treeview",
            background=[("selected", COLORES["acento"])],
            foreground=[("selected", "white")],
        )

        tree = ttk.Treeview(frame, columns=columnas, show="headings",
                            style="Custom.Treeview")

        for col in columnas:
            tree.heading(col, text=col)
            tree.column(col, width=200, anchor="w")

        tree.tag_configure("par",   background=COLORES["bg_tarjeta"])
        tree.tag_configure("impar", background=COLORES["bg_oscuro"])

        sb_y = ttk.Scrollbar(frame, orient="vertical",   command=tree.yview)
        sb_x = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        sb_y.pack(side="right",  fill="y")
        sb_x.pack(side="bottom", fill="x")
        tree.pack(side="left", fill="both", expand=True)

        return tree

    def _estilo_notebook(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",
            background=COLORES["bg_oscuro"],
            borderwidth=0,
        )
        style.configure("TNotebook.Tab",
            background=COLORES["bg_panel"],
            foreground=COLORES["texto_dim"],
            padding=(12, 6),
            font=FUENTE_NORMAL,
        )
        style.map("TNotebook.Tab",
            background=[("selected", COLORES["bg_tarjeta"])],
            foreground=[("selected", COLORES["acento"])],
        )


# ══════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════

if __name__ == "__main__":
    app = IFCAuditorApp()
    app.mainloop()
