"""
================================================================================
SMART CV FILTER - CLOUD EDITION (GROQ LPU™ POWERED)
================================================================================
Author: Tebagl
Date: April 2026
Version: 2.0 (Cloud Migration)

DESCRIPTION:
An intelligent GUI-based recruitment tool that automates resume screening.
This version utilizes the Groq Cloud API (Llama 3.1) for high-performance 
inference, significantly reducing local RAM and CPU consumption.

KEY FEATURES:
- Multithreaded Processing: Keeps the UI responsive during API calls.
- Groq Cloud Integration: Near-instant CV analysis (LPU™ technology).
- X11 Force-Rendering: Bypasses Wayland/Linux segmentation faults.
- Dynamic Result Management: Real-time candidate scoring and CSV logging.

DEPENDENCIES:
- CustomTkinter: Modern GUI framework.
- Requests: API communication.
- Python-Dotenv: Secure API key management via .env.
- Subprocess: System-level PDF/Docx viewing.

USAGE:
Run with 'python3 src/frontend/main_gui.py'. 
Requires a valid GROQ_API_KEY in the root .env file.
================================================================================
"""

# 1. Ajustes del Sistema Operativo
import os
os.environ["GDK_BACKEND"] = "x11"

# 2. Librerías Estándar de Python
import sys
import threading
import logging
import queue
import platform
import subprocess
from pathlib import Path
import time

# 3. Librerías de Interfaz Gráfica
import tkinter
import customtkinter as ctk


# --- Configuración de Rutas ---
def get_resource_path():
    """Ruta para archivos internos (código, iconos, etc.)"""
    if getattr(sys, 'frozen', False):
        # Estamos en el ejecutable
        return sys._MEIPASS
    
    # Estamos en desarrollo: subimos desde src/frontend/ a la raíz
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

def get_executable_path():
    """Ruta donde reside el archivo .exe o el binario (para carpetas de salida)"""
    if getattr(sys, 'frozen', False):
        # Si es el ejecutable, queremos la carpeta donde está el archivo físico
        return os.path.dirname(sys.executable)
    # Si es modo desarrollo, usamos la raíz del proyecto
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Definimos las dos rutas críticas
resource_path = get_resource_path()    
executable_path = get_executable_path() # Para crear 'procesos_seleccion'

# Importante: los imports del backend deben buscarse en resource_path
sys.path.insert(0, resource_path)

# Importar el backend
from src.backend.cv_handler import CVHandler
from src.backend.analyzer import CVAnalyzer
from src.backend.process_manager import ProcessManager

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Abrir el archivo conf.env
from dotenv import load_dotenv

# Fuerza la carga del archivo ANTES de que la interfaz decida qué mostrar
script_dir = os.path.dirname(os.path.abspath(__file__))
# Si main_gui.py está en src/frontend, subimos dos niveles
root_dir = os.path.dirname(os.path.dirname(script_dir)) 
dotenv_path = os.path.join(root_dir, 'conf.env')


class SmartCVFilterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw()  # Evita que la ventana parpadee antes de configurar todo

        # 1. Configuración de la Ventana Principal (Establece la raíz de TK)
        ctk.set_appearance_mode("dark")
        self.configure(fg_color="#1a1a1a")
        self.title("Smart CV Filter")
        self.geometry("900x700")
        

        # 2. INICIALIZACIÓN DE RUTAS Y VARIABLES (Obligatorio antes de widgets)
        self.default_dest_path = os.path.join(executable_path, "procesos_seleccion")
        if not os.path.exists(self.default_dest_path):
            os.makedirs(self.default_dest_path)
            
        self.input_folder = ctk.StringVar(value="")
        self.results_dir = ""
        self.api_key = None
        self.log_queue = queue.Queue()

        # 2. INICIALIZACIÓN DE VARIABLES DE CONTROL (Obligatorio antes de widgets)
        self.input_folder = ctk.StringVar(value="")
        self.api_key = None
            # Colas de comunicación (Indispensable para el hilo de log_text)
        self.log_queue = queue.Queue()

        # 3. Inicialización de Backend y Estado
        self.analyzer = CVAnalyzer()
        self.cv_handler = CVHandler(self.analyzer)
        self.api_key = None
        self.process_manager = ProcessManager(executable_path, self.cv_handler)
        
        # 4. Creación de Interfaz (Dibuja los widgets antes de cualquier diálogo)
        self.create_widgets()
        self.update_idletasks()
        
        # Mostrar la ventana ya renderizada en negro
        self.deiconify()

        # 5. Iniciar consumidores de colas
        self.check_queues()

        # 6. Verificación de Configuración con retraso (SOLUCIÓN VENTANA DOBLE)
        self.after(200, self.verificar_configuracion_inicial)

    def verificar_configuracion_inicial(self):
        """Valida la API Key sin crear ventanas CTk adicionales."""
        if self.analyzer.api_key:
            self.api_key = self.analyzer.api_key
            self.log_mensaje("✅ API Key cargada correctamente desde conf.env")
        else:
            self.api_key = self.solicitar_api_key()
            
        if self.api_key:
            # ACTUALIZACIÓN: Solo el analizador necesita gestionar la clave directamente
            self.analyzer.set_api_key(self.api_key)
            # self.cv_handler.set_api_key(self.api_key)  <-- ELIMINA O COMENTA ESTA LÍNEA
        else:
            self.log_mensaje("🛑 No se proporcionó API Key.")

    def log_mensaje(self, texto):
        """Método auxiliar para escribir en el log de la UI de forma segura"""
        if hasattr(self, 'log_text'):
            self.log_text.insert("end", f"{texto}\n")
            self.log_text.see("end")

    def create_widgets(self):
        # Frame principal con padding
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        # --- NUEVA SECCIÓN: DATOS DEL PROCESO ---
        process_info_frame = ctk.CTkFrame(main_frame)
        process_info_frame.pack(fill="x", padx=10, pady=5)

        # Campo Título
        ctk.CTkLabel(process_info_frame, text="📌 Puesto:", font=("Arial", 12, "bold")).pack(side="left", padx=10)
        self.entry_puesto = ctk.CTkEntry(process_info_frame, placeholder_text="Ej: Senior Data Engineer", width=200)
        self.entry_puesto.pack(side="left", padx=5)

        # Campo Fecha (por defecto hoy)
        from datetime import datetime
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        ctk.CTkLabel(process_info_frame, text="📅 Fecha:", font=("Arial", 12, "bold")).pack(side="left", padx=10)
        self.entry_fecha = ctk.CTkEntry(process_info_frame, width=120)
        self.entry_fecha.insert(0, fecha_hoy)
        self.entry_fecha.configure(state="readonly") # 🔒 Bloqueado desde el inicio
        self.entry_fecha.pack(side="left", padx=5)

        # --- SECCIÓN 1: CARPETA DE ENTRADA (ARRIBA) ---
        folder_frame = ctk.CTkFrame(main_frame)
        folder_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(folder_frame, text="📂 Carpeta de entrada:", font=("Arial", 12, "bold")).pack(side="left", padx=10)
        ctk.CTkEntry(folder_frame, textvariable=self.input_folder, width=350).pack(side="left", padx=5, expand=True, fill="x")
        ctk.CTkButton(folder_frame, text="Explorar", width=100, command=self.select_input_folder).pack(side="right", padx=10)

        # --- SECCIÓN: CARPETA DE DESTINO (En create_widgets) ---
        dest_frame = ctk.CTkFrame(main_frame)
        dest_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(dest_frame, text="🎯 Destino:", font=("Arial", 12, "bold")).pack(side="left", padx=10)

        self.entry_destino = ctk.CTkEntry(dest_frame, width=350)
        # Mostramos la carpeta MADRE por defecto
        self.entry_destino.insert(0, self.default_dest_path) 
        self.entry_destino.pack(side="left", padx=5, expand=True, fill="x")

        ctk.CTkButton(dest_frame, text="Explorar", width=100, command=self.select_destination_folder).pack(side="right", padx=10)

        # --- SECCIÓN 2: CONTENEDOR MEDIO (COLUMNAS) ---
        mid_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        mid_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Configuramos el peso de las columnas (60% izquierda, 40% derecha)
        mid_container.columnconfigure(0, weight=6)
        mid_container.columnconfigure(1, weight=4)
        mid_container.rowconfigure(0, weight=1)

        # --- COLUMNA IZQUIERDA (JD + BOTÓN) ---
        left_column = ctk.CTkFrame(mid_container, fg_color="transparent")
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        
        ctk.CTkLabel(left_column, text="📝 Descripción del puesto:", font=("Arial", 13, "bold")).pack(anchor="w", pady=(0, 5))
        
        # Textbox de JD
        self.jd_textbox = ctk.CTkTextbox(left_column, border_width=2)
        self.jd_textbox.pack(fill="both", expand=True, pady=(0, 10))
        
        # Menú de clic derecho
        self.menu_pegar = tkinter.Menu(self, tearoff=0, bg="#2b2b2b", fg="white", activebackground="#1f538d", bd=0)
        self.menu_pegar.add_command(label="  📋 Pegar Texto  ", command=self.pegar_texto)
        self.jd_textbox.bind("<Button-3>", self.mostrar_menu)

        # Botón Clasificar (Debajo de la JD)
        self.btn_analyze = ctk.CTkButton(
            left_column, 
            text="🚀 CLASIFICAR CVS", 
            font=("Arial", 14, "bold"), 
            height=45, 
            command=self.run_analysis
        )
        self.btn_analyze.pack(fill="x")

        # --- COLUMNA DERECHA (CVS ACEPTADOS) ---
        right_column = ctk.CTkFrame(mid_container)
        right_column.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        
        self.candidates_list = ctk.CTkScrollableFrame(right_column, label_text="CVs Aceptados")
        self.candidates_list.pack(fill="both", expand=True, padx=5, pady=5)

        # --- SECCIÓN 3: CONSOLA DE LOGS (ABAJO) ---
        console_frame = ctk.CTkFrame(main_frame)
        console_frame.pack(fill="x", side="bottom", padx=10, pady=(5, 10))
        
        ctk.CTkLabel(console_frame, text="🖥️ Log de procesamiento:", font=("Arial", 11, "bold")).pack(anchor="w", padx=10, pady=(5, 0))
        self.log_text = ctk.CTkTextbox(console_frame, height=120, fg_color="#1a1a1a", text_color="#00ff00", font=("Courier", 12),wrap="word")
        self.log_text.pack(fill="x", padx=10, pady=10)

    # --- Funciones de Soporte para Clic Derecho ---
    def mostrar_menu(self, event):
        """Muestra el menú con un pequeño margen para evitar clics accidentales"""
        try:
            # Añadimos +2 píxeles de margen en X e Y. 
            # Esto separa el cursor de la primera opción del menú.
            self.menu_pegar.tk_popup(event.x_root + 2, event.y_root + 2)
        finally:
            # Esto asegura que el menú libere el "foco" correctamente
            self.menu_pegar.grab_release()

    def pegar_texto(self):
        """Pega el texto asegurándose de limpiar el portapapeles de caracteres extra"""
        try:
            # Obtenemos el contenido del portapapeles
            texto = self.clipboard_get()
            if texto:
                # Insertamos en la posición actual del cursor ("insert")
                self.jd_textbox.insert("insert", texto)
                # Opcional: Desplazar la vista al final del texto pegado
                self.jd_textbox.see("end")
        except Exception as e:
            # Si el portapapeles no tiene texto (ej. una imagen), no hace nada
            pass
    

    def select_input_folder(self):
        from tkinter import filedialog
        import os
        
        # 1. Localizamos la ruta del Escritorio de forma dinámica
        # Esto funciona en Windows, macOS y Linux
        desktop_path = os.path.join(os.path.expanduser("~"), "Documents")
        
        # 2. Verificamos si existe (por si el SO tiene un nombre distinto)
        if not os.path.exists(desktop_path):
            desktop_path = os.path.expanduser("~") # Si no hay escritorio, abre su carpeta personal

        # 3. Abrimos el buscador empezando en el escritorio (initialdir)
        path = filedialog.askdirectory(
            initialdir=desktop_path,
            title="Selecciona la carpeta con los CVs"
        )
        
        if path:
            self.input_folder.set(path)


    def select_destination_folder(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(initialdir=self.default_dest_path, title="Seleccionar Proceso")
        
        if path:
            self.entry_destino.delete(0, "end")
            self.entry_destino.insert(0, path)
            
            # 1. 📂 Detectar si es un proceso existente (buscamos la carpeta RECLUTADOS)
            ruta_reclutados = os.path.join(path, "RECLUTADOS")
            if os.path.exists(ruta_reclutados):
                self.results_dir = ruta_reclutados
                
                # 2. 📅 Sincronizar FECHA y PUESTO desde el nombre de la carpeta
                nombre_folder = os.path.basename(path)
                if len(nombre_folder) >= 10 and "-" in nombre_folder:
                    fecha_orig = nombre_folder[:10]
                    # El puesto suele ser lo que va después del primer "_" (ej: 2026-04-10_Contable)
                    puesto_orig = nombre_folder[11:].replace("_", " ") if len(nombre_folder) > 11 else ""
                    
                    # Actualizar Fecha
                    self.entry_fecha.configure(state="normal")
                    self.entry_fecha.delete(0, "end")
                    self.entry_fecha.insert(0, fecha_orig)
                    self.entry_fecha.configure(state="readonly")
                    
                    # Actualizar Puesto
                    self.entry_puesto.delete(0, "end")
                    self.entry_puesto.insert(0, puesto_orig)

                # 3. 📝 Cargar DESCRIPCIÓN (JD) desde el archivo .txt
                ruta_jd = os.path.join(path, "descripcion_puesto.txt")
                if os.path.exists(ruta_jd):
                    try:
                        with open(ruta_jd, "r", encoding="utf-8") as f:
                            contenido_jd = f.read()
                        self.jd_textbox.delete("0.0", "end")
                        self.jd_textbox.insert("0.0", contenido_jd)
                    except Exception as e:
                        logger.error(f"Error al leer JD: {e}")

                # 4. ⭐ Cargar lista de CANDIDATOS
                self.update_top_candidates()
                self.log_text.insert("end", f"✅ Proceso '{puesto_orig}' cargado correctamente.\n")

    # --- Lógica de la Aplicación ---
    
    def solicitar_api_key(self):
        """
        Crea una ventana emergente para la API Key con soporte garantizado
        para clic derecho (pegar) mediante inyección de eventos.
        """
        dialog = ctk.CTkInputDialog(
            text="Introduce tu API Key de Groq:", 
            title="Configuración inicial"
        )
        
        # 1. Creamos el menú contextual una sola vez
        menu_contextual = tkinter.Menu(self, tearoff=0)
        
        # 2. Función para inyectar el comando de pegado
        def ejecutar_pegado(target):
            try:
                # Intentamos usar el comando universal de pegado del sistema
                target.event_generate("<<Paste>>")
            except:
                # Fallback: intentar leer directamente del portapapeles de la app
                try:
                    texto = self.clipboard_get()
                    target.insert(tkinter.INSERT, texto)
                except:
                    pass

        # 3. Localización profunda del widget de entrada real
        def configurar_eventos(parent):
            for child in parent.winfo_children():
                # Si encontramos el Entry (ya sea de CTk o de Tkinter puro)
                if isinstance(child, (ctk.CTkEntry, tkinter.Entry)):
                    # Configurar menú para este widget específico
                    menu_contextual.delete(0, "end")
                    menu_contextual.add_command(label="📋 Pegar", command=lambda: ejecutar_pegado(child))
                    menu_contextual.add_command(label="✂️ Copiar", command=lambda: child.event_generate("<<Copy>>"))

                    def mostrar_menu(event):
                        child.focus_set() # Obligatorio para que sepa dónde pegar
                        menu_contextual.tk_popup(event.x_root, event.y_root)
                        return "break" # Evita que otros widgets procesen el clic

                    # Vinculamos a todas las variantes de botón derecho/central
                    child.bind("<Button-3>", mostrar_menu) # Windows/Linux
                    child.bind("<Button-2>", mostrar_menu) # macOS/Linux Middle click
                    
                # Continuar buscando en profundidad
                configurar_eventos(child)

        # Lanzamos la configuración sobre el diálogo
        self.after(100, lambda: configurar_eventos(dialog))
        
        return dialog.get_input()

    def update_top_candidates(self):
        # Limpiamos la lista actual
        for widget in self.candidates_list.winfo_children():
            widget.destroy()

        if not os.path.exists(self.results_dir):
            return

        try:
            # 1. Obtenemos la lista de archivos
            archivos = [f for f in os.listdir(self.results_dir) 
                       if f.lower().endswith(('.txt', '.pdf', '.docx'))]
            
            # 2. ORDENAR: Los más altos arriba
            archivos.sort(reverse=True)
            
            for nombre in archivos:
                # --- 🛡️ PARCHE DE SEGURIDAD: FILTRO DE SCORE ---
                # Intentamos extraer el número del principio del nombre (ej: "70_C.V.pdf")
                try:
                    score_str = nombre.split('_')[0]
                    score_val = int(score_str)
                except (ValueError, IndexError):
                    score_val = 0 # Si no hay número, lo ignoramos

                # SOLO añadimos a la lista de la derecha si supera el umbral (60%)
                if score_val >= 60:
                    ruta_completa = os.path.join(self.results_dir, nombre)
                    display_name = nombre 

                    btn = ctk.CTkButton(
                        self.candidates_list, 
                        text=f"⭐ {display_name}",
                        fg_color="#34495e",
                        hover_color="#1f538d",
                        anchor="w",
                        command=lambda r=ruta_completa: self.open_candidate_cv(r)
                    )
                    btn.pack(fill="x", pady=2, padx=5)    
        except Exception as e:
            logger.error(f"Error actualizando lista visual: {e}")


    def open_candidate_cv(self, file_path):
        if not os.path.exists(file_path):
            self.log_text.insert("end", f"⚠️ Archivo no encontrado: {file_path}\n")
            return
        
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin": # macOS
                subprocess.call(("open", file_path))
            else: # 🐧 Linux (Aquí es donde estaba el problema)
                # 🛡️ "Limpiamos" las librerías internas antes de llamar al sistema
                env = dict(os.environ)
                # Eliminamos la ruta de librerías de PyInstaller para este proceso
                if "LD_LIBRARY_PATH" in env:
                    del env["LD_LIBRARY_PATH"]
                
                # Ejecutamos xdg-open con el entorno limpio
                subprocess.Popen(["xdg-open", file_path], env=env)
                
        except Exception as e:
            self.log_text.insert("end", f"❌ Error al abrir: {e}\n")


    
    def run_analysis(self):
        # Captura los datos de la interfaz
        puesto = self.entry_puesto.get().strip()
        ruta_destino_base = self.entry_destino.get().strip() 
        folder_path_entrada = self.input_folder.get().strip()
        user_description = self.jd_textbox.get("0.0", "end").strip()

        # Validaciones de UI (Si falta algo, sale)
        if not folder_path_entrada or not puesto or not user_description or not ruta_destino_base:
            self.log_text.insert("end", "⚠️ ERROR: Faltan datos (Entrada, Destino, Puesto o Descripción).\n")
            self.log_text.see("end")
            return
        
        self.log_text.insert("end", "⏳ Preparando entorno de análisis...\n")
        self.log_text.see("end")

        # El Manager crea o recupera la carpeta del proceso
        main_folder, self.results_dir = self.process_manager.configure_process(puesto, ruta_destino_base)

        # Sincronización visual de la fecha y la lista
        nombre_carpeta = os.path.basename(main_folder)
        
        # Actualiza la fecha en el cuadro (por si es un proceso antiguo)
        if len(nombre_carpeta) >= 10 and nombre_carpeta.count("-") >= 2:
            fecha_detectada = nombre_carpeta[:10]
            self.entry_fecha.configure(state="normal")
            self.entry_fecha.delete(0, "end")
            self.entry_fecha.insert(0, fecha_detectada)
            self.entry_fecha.configure(state="readonly")

        # Muestra los CVs que ya estaban en la carpeta (Memoria Visual)
        self.update_top_candidates()

        # Guarda descripción y lanza el análisis
        self.process_manager.save_job_description(main_folder, user_description)

        # Bloquear botón e iniciar hilo de trabajo
        self.btn_analyze.configure(state="disabled")
        threading.Thread(target=self.analysis_worker, args=(user_description,), daemon=True).start()
        

    def analysis_worker(self, user_job_desc):
        try:

            folder_path = Path(self.input_folder.get())
            extensiones = [".txt", ".pdf", ".docx"]
            files = [f for f in folder_path.iterdir() if f.suffix.lower() in extensiones]
           
            if not files:
                self.log_queue.put("⚠️ No se encontraron archivos (PDF, DOCX, TXT) en la carpeta seleccionada.")
                self.log_queue.put("FIN")
                return

            self.log_queue.put(f"📑 Procesando {len(files)} candidatos...")

            for file_path in files:
                self.log_queue.put(f"🔍 Analizando: {file_path.name}")
                
                resultado = self.cv_handler.process_cv(str(file_path), user_job_desc)

                if resultado.get("status") == "success":
                    # Usamos .get() con valores por defecto para evitar CRASHES
                    score = resultado.get("score", 0)
                    motivo = resultado.get("motivo", "No se proporcionó explicación")
                    nombre = resultado.get("nombre", "Archivo")
                    
                    # 🟢 Pintar en el log 
                    self.log_queue.put(f"✅ SCORE -> {score}%")
                    self.log_queue.put(f"   💡 MOTIVO: {motivo}") 
                    self.log_queue.put("-" * 45)
                    self.log_queue.put("UPDATE_LIST")
                    
                
                else:
                    error_msg = resultado.get("reason", "Error desconocido")
                    self.log_queue.put(f"❌ Error en {file_path.name}: {error_msg}")
                
                self.log_queue.put("⏳Reseteando tokens de Groq(15s)...") 
                self.log_queue.put("-" * 40) # Una línea separadora un poco más larga

            self.log_queue.put("\n🎊 ¡Clasificación terminada!")
            self.log_queue.put("UPDATE_LIST")
            self.log_queue.put("FIN")

        except Exception as e:
            self.log_queue.put(f"❌ Error crítico: {e}")
            self.log_queue.put("FIN")


    def check_queues(self):
        try:
            while not self.log_queue.empty():
                msg = self.log_queue.get_nowait()
                if msg == "UPDATE_LIST":
                    self.update_top_candidates()
                elif msg == "FIN":
                    self.btn_analyze.configure(state="normal")
                else:
                    self.log_text.insert("end", f"{msg}\n")
                    self.log_text.see("end")
        except:
            pass
        self.after(100, self.check_queues)


if __name__ == "__main__":
    ctk.set_widget_scaling(1.0)  # Fuerza escala 1:1
    app = SmartCVFilterApp()
    # En lugar de fijarlo a lo bruto, usamos after para esperar 200ms
    # Esto suele evitar el Segmentation Fault en Linux
    app.after(200, lambda: ctk.set_appearance_mode("dark"))
    app.mainloop()