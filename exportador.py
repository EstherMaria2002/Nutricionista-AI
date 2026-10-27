"""
Exportación a PDF REAL (bug 9) con fpdf2 y a Google Calendar.

Causas del fallo original:
  1. `from google.oauth2... import` y `googleapiclient` estaban en el import del módulo: si no están
     instalados, `Exportador()` ni siquiera se importaba. Ahora se importan SOLO dentro de
     exportar_google_calendar().
  2. En main.py el botón estaba dentro de `if datos:` (el formulario solo devuelve datos en el rerun del
     submit); al pulsar el botón Streamlit relanzaba el script, `datos` era None y el bloque desaparecía.
     Ahora el plan vive en st.session_state y el PDF se genera como bytes -> st.download_button.
  3. `multi_cell(..., ln=True)` y la fuente "Arial" están obsoletas en fpdf2; texto con "•" o emojis rompe
     las fuentes core (latin-1). Se sanea el texto.
"""
import re
from datetime import date, datetime, timedelta
from typing import Dict, List

from fpdf import FPDF

from planificador import DIAS

DISCLAIMER = ("Nutricionista AI no sustituye el consejo de un profesional sanitario. Consulta a tu médico o "
              "dietista-nutricionista antes de iniciar cambios importantes.")
HORAS = {"Desayuno": 8, "Media mañana": 11, "Comida": 14, "Merienda": 17, "Cena": 21, "Recena": 22,
         "Postre": 15, "Bebida": 8}
TZ = "Europe/Madrid"


def _t(texto) -> str:
    """Saneado a latin-1 (fuentes core de PDF)."""
    texto = str(texto)
    for a, b in {"•": "-", "–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "→": "->", "×": "x",
                 "·": "-", "…": "...", "≈": "~", "≤": "<=", "≥": ">="}.items():
        texto = texto.replace(a, b)
    texto = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f]", "", texto)   # emojis
    return texto.encode("latin-1", "replace").decode("latin-1")


def nombre_archivo_pdf(datos: dict) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (datos.get("nombre_plan") or datos.get("nombre") or "plan").lower()
                  .translate(str.maketrans("áéíóúñü", "aeiounu"))).strip("-") or "plan"
    return f"menu-{slug}-{date.today().isoformat()}.pdf"


class _PDF(FPDF):
    titulo = ""

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110)
        self.cell(0, 6, _t(f"{self.titulo}  -  {date.today().strftime('%d/%m/%Y')}  -  Pagina {self.page_no()}"),
                  align="C")
        self.set_text_color(0)


class Exportador:
    def __init__(self):
        self.pdf = None

    # ------------------------------------------------------------------ helpers PDF
    def _h(self, pdf, texto, size=14, espacio=2):
        pdf.set_font("Helvetica", "B", size)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, size * 0.5 + 2, _t(texto), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(espacio)

    def _p(self, pdf, texto, size=10, estilo="", h=5):
        pdf.set_font("Helvetica", estilo, size)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, h, _t(texto), new_x="LMARGIN", new_y="NEXT")

    def _tabla_semana(self, pdf, plan, macros):
        cols = plan["columnas"]
        pdf.set_font("Helvetica", "", 8)
        with pdf.table(col_widths=[16] + [60 / len(cols) * 4.2 for _ in cols] + ([12] if macros else []),
                       text_align="LEFT", line_height=4.2, first_row_as_headings=True) as t:
            fila = t.row()
            for c in ["Dia"] + cols + (["kcal"] if macros else []):
                fila.cell(_t(c))
            for dia in DIAS:
                fila = t.row()
                fila.cell(_t(dia))
                for c in cols:
                    s = plan["menu"][dia].get(c)
                    if not s:
                        fila.cell("-")
                    elif s.get("fuera"):
                        fila.cell("Fuera de casa")
                    else:
                        x = f" x{s['factor']:g}" if s.get("factor", 1) != 1 else ""
                        extra = (f"\n{s['calorias']:.0f} kcal P{s['proteinas']:.0f} G{s['grasas']:.0f} C{s['carbos']:.0f}"
                                 if macros else "")
                        fila.cell(_t(s["nombre"] + x + extra))
                if macros:
                    fila.cell(f"{plan['totales_dia'][dia]['total']['calorias']:.0f}")

    def _lista_dias(self, pdf, plan, macros):
        for dia in DIAS:
            self._h(pdf, dia, 12, 1)
            for c in plan["columnas"]:
                s = plan["menu"][dia].get(c)
                if not s:
                    continue
                if s.get("fuera"):
                    self._p(pdf, f"  {c}: fuera de casa")
                    continue
                x = f" (x{s['factor']:g} racion)" if s.get("factor", 1) != 1 else ""
                m = (f" - {s['calorias']:.0f} kcal | P {s['proteinas']:.0f} g | G {s['grasas']:.0f} g | C {s['carbos']:.0f} g"
                     if macros else "")
                self._p(pdf, f"  {c}: {s['nombre']}{x}{m}")
                if s.get("ingredientes"):
                    self._p(pdf, "      Ingredientes: " + ", ".join(s["ingredientes"][:12]), 8, "I", 4)
            pdf.ln(2)

    def _recetas(self, pdf, recetas: List[Dict], macros=True):
        for i, r in enumerate(recetas, 1):
            if pdf.get_y() > pdf.h - 60:
                pdf.add_page()
            self._h(pdf, f"{i}. {r['nombre']}", 12, 1)
            meta = f"Tiempo: {r.get('tiempo_preparacion', '-')} min  |  Fuente: {r.get('fuente', '-')}"
            if macros:
                meta += (f"  |  Por racion: {r['calorias']:.0f} kcal, P {r['proteinas']:.0f} g, "
                         f"G {r['grasas']:.0f} g, C {r['carbos']:.0f} g")
            self._p(pdf, meta, 8, "I", 4)
            self._p(pdf, "Ingredientes: " + ", ".join(map(str, r.get("ingredientes", []))), 9)
            ins = r.get("instrucciones", "")
            self._p(pdf, "Instrucciones: " + (ins[:1500] + "..." if len(ins) > 1500 else ins), 9)
            pdf.ln(3)

    def _compra(self, pdf, plan, personas):
        self._h(pdf, f"Lista de la compra (para {personas} persona{'s' if personas != 1 else ''})", 13)
        self._p(pdf, "Las cantidades dependen de cada receta; multiplica segun el numero de personas.", 8, "I", 4)
        for cat, items in plan["lista_compra"].items():
            self._h(pdf, cat, 10, 1)
            for it in items:
                self._p(pdf, f"  [ ] {it}", 9, "", 4.5)
            pdf.ln(1)

    # ------------------------------------------------------------------ API pública
    def exportar_plan_pdf(self, plan: dict, datos: dict) -> bytes:
        """Devuelve los bytes de un PDF válido con TODO el plan según las opciones del Bloque 7."""
        obj = plan["objetivos"]
        formato = datos.get("formato_menu", "Tabla semanal")
        macros = bool(datos.get("macros_por_comida", True))
        titulo = datos.get("nombre_plan") or "Plan nutricional semanal"

        pdf = _PDF(orientation="L" if formato == "Tabla semanal" else "P", unit="mm", format="A4")
        pdf.titulo = _t(titulo)
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_title(_t(titulo))
        pdf.add_page()

        self._h(pdf, titulo, 20, 2)
        if datos.get("nombre"):
            self._p(pdf, f"Preparado para: {datos['nombre']}", 10, "I")
        self._p(pdf, f"Generado el {date.today().strftime('%d/%m/%Y')}", 9, "I")
        pdf.ln(2)
        self._h(pdf, "Objetivos diarios", 13, 1)
        self._p(pdf, f"{obj['kcal']} kcal  |  Proteinas {obj['proteinas']} g  |  Grasas {obj['grasas']} g  |  "
                     f"Carbohidratos {obj['carbos']} g   (TMB {obj['tmb']} kcal, TDEE {obj['tdee']} kcal)")
        if macros:
            p = plan["promedio_diario"]
            self._p(pdf, f"Promedio del menu: {p['calorias']:.0f} kcal | P {p['proteinas']:.0f} g | "
                         f"G {p['grasas']:.0f} g | C {p['carbos']:.0f} g", 9, "I")
        pdf.ln(3)

        if formato != "Solo lista de compra":
            self._h(pdf, "Menu semanal", 14, 2)
            if formato == "Tabla semanal":
                self._tabla_semana(pdf, plan, macros)
            else:
                self._lista_dias(pdf, plan, macros)
            if macros:
                pdf.ln(3)
                self._h(pdf, "Totales diarios vs objetivo", 12, 1)
                for dia in DIAS:
                    t, o, s = plan["totales_dia"][dia]["total"], plan["totales_dia"][dia]["objetivo"], \
                        plan["totales_dia"][dia]["semaforo"]
                    sem = lambda x: {"🟢": "OK", "🟡": "~", "🔴": "!!", "⚪": "-"}[x]
                    self._p(pdf, f"{dia}: {t['calorias']:.0f}/{o['calorias']} kcal [{sem(s['calorias'])}]  "
                                 f"P {t['proteinas']:.0f}/{o['proteinas']} [{sem(s['proteinas'])}]  "
                                 f"G {t['grasas']:.0f}/{o['grasas']} [{sem(s['grasas'])}]  "
                                 f"C {t['carbos']:.0f}/{o['carbos']} [{sem(s['carbos'])}]", 9)
                w = plan["totales_semana"]
                self._p(pdf, f"SEMANA: {w['calorias']:.0f} kcal | P {w['proteinas']:.0f} g | G {w['grasas']:.0f} g | "
                             f"C {w['carbos']:.0f} g", 10, "B")

        if datos.get("recetas_detalladas", True) and formato != "Solo lista de compra":
            pdf.add_page()
            self._h(pdf, "Recetas detalladas", 14, 2)
            self._recetas(pdf, plan["recetas_usadas"], macros)

        if datos.get("lista_compra", True) or formato == "Solo lista de compra":
            if formato != "Solo lista de compra":
                pdf.add_page()
            self._compra(pdf, plan, datos.get("personas", 1))

        if plan.get("avisos"):
            pdf.ln(3)
            self._h(pdf, "Avisos", 11, 1)
            for a in plan["avisos"] + plan["objetivos"].get("avisos", []):
                self._p(pdf, f"- {a}", 8, "", 4)
        pdf.ln(4)
        self._p(pdf, DISCLAIMER, 8, "I", 4)

        return bytes(pdf.output())

    def exportar_recetas_pdf(self, recetas: list, nombre_archivo: str = "recetas_completas.pdf") -> str:
        """Compatibilidad: solo recetas, a disco."""
        pdf = _PDF(unit="mm", format="A4")
        pdf.titulo = "Recetas"
        pdf.add_page()
        self._h(pdf, "Recetas", 18)
        self._recetas(pdf, recetas)
        pdf.output(nombre_archivo)
        return nombre_archivo

    def exportar_google_calendar(self, plan: dict, credenciales_file: str = "credentials.json"):
        """Exporta el menú (estructura del plan) a Google Calendar. Imports perezosos (ver cabecera)."""
        import os
        import pickle
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credenciales_file,
                                                                 ['https://www.googleapis.com/auth/calendar'])
                creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        service = build('calendar', 'v3', credentials=creds)
        cal = service.calendars().insert(body={'summary': 'Plan Nutricional Semanal', 'timeZone': TZ}).execute()
        hoy = datetime.now()
        for i, dia in enumerate(DIAS):
            f = hoy + timedelta(days=i)
            for comida, s in plan["menu"][dia].items():
                if s.get("fuera"):
                    continue
                h = HORAS.get(comida, 12)
                ini = datetime(f.year, f.month, f.day, h, 0)
                service.events().insert(calendarId=cal['id'], body={
                    'summary': f"{comida}: {s['nombre']}",
                    'description': f"Ingredientes: {', '.join(s.get('ingredientes', [])[:8])}\n"
                                   f"{s['calorias']:.0f} kcal | P {s['proteinas']:.0f} g | G {s['grasas']:.0f} g | C {s['carbos']:.0f} g",
                    'start': {'dateTime': ini.isoformat(), 'timeZone': TZ},
                    'end': {'dateTime': (ini + timedelta(minutes=45)).isoformat(), 'timeZone': TZ},
                    'reminders': {'useDefault': True},
                }).execute()
        return cal['id']
