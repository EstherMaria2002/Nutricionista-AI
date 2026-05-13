from fpdf import FPDF
import json
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import pickle

class Exportador:
    def __init__(self):
        self.pdf = None
    
    def exportar_menu_pdf(self, menu: str, recetas_completas: list, nombre_archivo: str = "menu_semanal.pdf"):
        """Exporta el menú semanal a PDF con las recetas detalladas"""
        self.pdf = FPDF()
        self.pdf.add_page()
        self.pdf.set_auto_page_break(auto=True, margin=15)
        
        # Título
        self.pdf.set_font("Arial", "B", 20)
        self.pdf.cell(0, 10, "Plan Nutricional Semanal", ln=True, align="C")
        self.pdf.ln(10)
        
        # Menú semanal
        self.pdf.set_font("Arial", "B", 16)
        self.pdf.cell(0, 10, "Menú de la Semana", ln=True)
        self.pdf.set_font("Arial", "", 12)
        
        # Procesar menú markdown a texto
        for linea in menu.split('\n'):
            self.pdf.multi_cell(0, 8, linea)
            self.pdf.ln(2)
        
        self.pdf.add_page()
        
        # Recetas detalladas
        self.pdf.set_font("Arial", "B", 18)
        self.pdf.cell(0, 10, "Recetas Detalladas", ln=True, align="C")
        self.pdf.ln(5)
        
        for idx, receta in enumerate(recetas_completas[:20], 1):  # Límite de 20 recetas para PDF
            self.pdf.set_font("Arial", "B", 14)
            self.pdf.cell(0, 8, f"{idx}. {receta['nombre']}", ln=True)
            self.pdf.ln(2)
            
            self.pdf.set_font("Arial", "B", 11)
            self.pdf.cell(0, 6, "Ingredientes:", ln=True)
            self.pdf.set_font("Arial", "", 11)
            for ing in receta['ingredientes'][:10]:  # Límite de 10 ingredientes
                self.pdf.cell(0, 5, f"  • {ing}", ln=True)
            
            self.pdf.ln(2)
            self.pdf.set_font("Arial", "B", 11)
            self.pdf.cell(0, 6, "Instrucciones:", ln=True)
            self.pdf.set_font("Arial", "", 11)
            
            # Instrucciones truncadas
            instrucciones = receta['instrucciones'][:500] + "..." if len(receta['instrucciones']) > 500 else receta['instrucciones']
            self.pdf.multi_cell(0, 5, instrucciones)
            
            # Información nutricional
            self.pdf.set_font("Arial", "I", 10)
            self.pdf.cell(0, 5, f"Calorías: {receta['calorias']:.0f} kcal | "
                               f"Proteínas: {receta['proteinas']:.1f}g | "
                               f"Grasas: {receta['grasas']:.1f}g | "
                               f"Carbos: {receta['carbos']:.1f}g", ln=True)
            
            self.pdf.ln(8)
            
            # Nueva página si es necesario
            if self.pdf.get_y() > 250:
                self.pdf.add_page()
        
        self.pdf.output(nombre_archivo)
        return nombre_archivo
    
    def exportar_recetas_pdf(self, recetas: list, nombre_archivo: str = "recetas_completas.pdf"):
        """Exporta solo las recetas con todos los detalles"""
        self.pdf = FPDF()
        
        for receta in recetas:
            self.pdf.add_page()
            
            # Título de receta
            self.pdf.set_font("Arial", "B", 18)
            self.pdf.cell(0, 10, receta['nombre'], ln=True, align="C")
            self.pdf.ln(5)
            
            # Fuente
            self.pdf.set_font("Arial", "I", 10)
            self.pdf.cell(0, 5, f"Fuente: {receta.get('fuente', 'Desconocida')}", ln=True)
            self.pdf.ln(5)
            
            # Tiempo de preparación
            if 'tiempo_preparacion' in receta:
                self.pdf.set_font("Arial", "B", 11)
                self.pdf.cell(0, 6, f"Tiempo de preparación: {receta['tiempo_preparacion']} minutos", ln=True)
                self.pdf.ln(3)
            
            # Ingredientes
            self.pdf.set_font("Arial", "B", 14)
            self.pdf.cell(0, 8, "Ingredientes:", ln=True)
            self.pdf.set_font("Arial", "", 11)
            for ing in receta['ingredientes']:
                self.pdf.cell(0, 6, f"• {ing}", ln=True)
            
            self.pdf.ln(5)
            
            # Instrucciones
            self.pdf.set_font("Arial", "B", 14)
            self.pdf.cell(0, 8, "Instrucciones:", ln=True)
            self.pdf.set_font("Arial", "", 11)
            
            # Dividir instrucciones en pasos
            instrucciones = receta['instrucciones']
            if '.' in instrucciones:
                pasos = instrucciones.split('.')
                for paso in pasos:
                    if paso.strip():
                        self.pdf.multi_cell(0, 6, f"{paso.strip()}.", ln=True)
            else:
                self.pdf.multi_cell(0, 6, instrucciones, ln=True)
            
            self.pdf.ln(5)
            
            # Información nutricional
            self.pdf.set_font("Arial", "B", 12)
            self.pdf.cell(0, 6, "Información Nutricional (por porción):", ln=True)
            self.pdf.set_font("Arial", "", 11)
            self.pdf.cell(0, 6, f"Calorías: {receta['calorias']:.0f} kcal", ln=True)
            self.pdf.cell(0, 6, f"Proteínas: {receta['proteinas']:.1f}g", ln=True)
            self.pdf.cell(0, 6, f"Grasas: {receta['grasas']:.1f}g", ln=True)
            self.pdf.cell(0, 6, f"Carbohidratos: {receta['carbos']:.1f}g", ln=True)
        
        self.pdf.output(nombre_archivo)
        return nombre_archivo
    
    def exportar_google_calendar(self, menu_estructurado: dict, credenciales_file: str = "credentials.json"):
        """Exporta el menú a Google Calendar"""
        creds = None
        
        # Cargar credenciales guardadas
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # Si no hay credenciales válidas, autenticar
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                from google_auth_oauthlib.flow import InstalledAppFlow
                flow = InstalledAppFlow.from_client_secrets_file(
                    credenciales_file, ['https://www.googleapis.com/auth/calendar']
                )
                creds = flow.run_local_server(port=0)
            
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        service = build('calendar', 'v3', credentials=creds)
        
        # Crear calendario para el plan nutricional
        calendar = {
            'summary': 'Plan Nutricional Semanal',
            'timeZone': 'America/Mexico_City'
        }
        created_calendar = service.calendars().insert(body=calendar).execute()
        calendar_id = created_calendar['id']
        
        # Añadir eventos por día
        for dia, comidas in menu_estructurado.items():
            fecha = datetime.now() + timedelta(days=list(menu_estructurado.keys()).index(dia))
            
            for comida, receta in comidas.items():
                evento = {
                    'summary': f"{comida}: {receta['nombre']}",
                    'description': f"Ingredientes: {', '.join(receta['ingredientes'][:5])}\n\n"
                                 f"Instrucciones: {receta['instrucciones'][:200]}...\n\n"
                                 f"Calorías: {receta['calorias']} kcal | "
                                 f"Proteínas: {receta['proteinas']}g | "
                                 f"Grasas: {receta['grasas']}g | "
                                 f"Carbos: {receta['carbos']}g",
                    'start': {
                        'dateTime': datetime(fecha.year, fecha.month, fecha.day, 8, 0).isoformat(),
                        'timeZone': 'America/Mexico_City',
                    },
                    'end': {
                        'dateTime': datetime(fecha.year, fecha.month, fecha.day, 9, 0).isoformat(),
                        'timeZone': 'America/Mexico_City',
                    },
                    'reminders': {
                        'useDefault': True,
                    },
                }
                
                service.events().insert(calendarId=calendar_id, body=evento).execute()
        
        return calendar_id