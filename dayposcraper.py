import json
import time
import threading
import customtkinter as ctk
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException

JS_EXTRACTION_SCRIPT = """
function get_current_question_data() {
    if (typeof m === 'undefined' || typeof sec === 'undefined' || typeof vcue === 'undefined') {
        return { error: 'Variables JS esenciales no cargadas' };
    }
    
    try {
        const e = Math.abs(sec[sa][ca]) - 1;
        const cadenaCorrecta = vcue("c", e);
        
        let marcador = '2';
        if (!cadenaCorrecta.includes('2') && cadenaCorrecta.includes('1')) {
            marcador = '1';
        }
        
        let originalCorrectIndices = [];
        for (let i = 0; i < cadenaCorrecta.length; i++) {
            if (cadenaCorrecta[i] === marcador) {
                originalCorrectIndices.push(i);
            }
        }

        const preguntaElement = document.getElementById('pri' + m);
        const textoPregunta = preguntaElement ? preguntaElement.innerText.trim() : 'N/D';
        const opcionesElements = document.querySelectorAll('#cuestiones' + m + ' tr td:nth-child(3)');
        const opcionesTexto = Array.from(opcionesElements).map(el => el.innerText.trim());

        let respuestasCorrectasTexto = [];

        if (typeof mez !== 'undefined' && Array.isArray(mez) && mez.length === opcionesTexto.length) {
            for (const originalIndex of originalCorrectIndices) {
                const posicionPantalla = mez.findIndex(val => val === originalIndex);
                if (posicionPantalla !== -1) {
                    respuestasCorrectasTexto.push(opcionesTexto[posicionPantalla]);
                }
            }
        } else {
             respuestasCorrectasTexto = originalCorrectIndices.map(i => opcionesTexto[i] || 'N/D');
        }
        
        return {
            pregunta: textoPregunta,
            opciones: opcionesTexto,
            respuesta: respuestasCorrectasTexto,
            id_pregunta: e,
            cadena_marcadores: cadenaCorrecta
        };

    } catch (error) {
        return { error: error.toString(), detalle: "Error al acceder a las variables del test." };
    }
}
return get_current_question_data();
"""

class ScraperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración de la ventana
        self.title("Scraper Daypo")
        self.geometry("600x400")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.driver = None
        self.is_running = False
        self.total_questions = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text="URL del Test:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.url_entry = ctk.CTkEntry(input_frame, placeholder_text="Ej: https://www.daypo.com/examen-intelectual-isep-santa-fe.html#test")
        self.url_entry.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="ew")
        
        ctk.CTkLabel(input_frame, text="Archivo JSON:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.file_entry = ctk.CTkEntry(input_frame, placeholder_text="Ej: resultados.json")
        self.file_entry.grid(row=1, column=1, padx=(0, 10), pady=10, sticky="ew")

        control_frame = ctk.CTkFrame(self)
        control_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        control_frame.grid_columnconfigure((0, 1), weight=1)

        self.start_button = ctk.CTkButton(control_frame, text="Scrapear", command=self.start_scraping_thread)
        self.start_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.stop_button = ctk.CTkButton(control_frame, text="Detener", command=self.stop_scraping, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(self, mode="determinate")
        self.progress_bar.grid(row=2, column=0, padx=10, pady=(5, 0), sticky="ew")
        self.progress_bar.set(0)
        
        ctk.CTkLabel(self, text="Registro").grid(row=3, column=0, padx=10, pady=(5, 0), sticky="sw")
        self.log_textbox = ctk.CTkTextbox(self, state="disabled")
        self.log_textbox.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="nsew")

    def log(self, message):
        def update_log():
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", message + "\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
        
        self.after(0, update_log)

    def _normalize_url(self, url):
        return re.sub(r'\.html(#.*)?$', '.html#test', url, flags=re.IGNORECASE)

    def start_scraping_thread(self):
        if self.is_running:
            return

        url_input = self.url_entry.get()
        self.url = self._normalize_url(url_input)
        self.file_name = self.file_entry.get()
        
        if not self.url or not self.file_name:
            self.log("ERROR: La URL y el nombre del archivo son obligatorios.")
            return

        self.is_running = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log(f"URL normalizada: {self.url}")
        self.log(f"Iniciando extracción...")

        self.after(0, lambda: self.progress_bar.set(0))
        threading.Thread(target=self._run_scraper_logic, daemon=True).start()

    def stop_scraping(self):
        self.is_running = False
        self.log("Deteniendo...")
        if self.driver:
            self.driver.quit()
            self.driver = None
        
        self.after(0, lambda: self.progress_bar.set(0))
        self.stop_button.configure(state="disabled")
        self.start_button.configure(state="normal")
        
    def _run_scraper_logic(self):
        resultados = []
        
        try:
            self.driver = webdriver.Chrome() 
            self.driver.get(self.url)
            time.sleep(3) 
            
            try:
                cuestion_text = self.driver.find_element(By.ID, "cuestion").text
                total_str = cuestion_text.split('/')[-1]
                self.total_questions = int(total_str.strip())
                self.log(f"Cuestionario de {self.total_questions} preguntas.")
            except (NoSuchElementException, ValueError):
                self.log("ERROR: No se pudo obtener el número total de preguntas (ID 'cuestion'). Abortando.")
                return

            while self.is_running:
                if len(resultados) >= self.total_questions and self.total_questions > 0:
                    self.log(f"Scraping terminado.")
                    break
                
                datos_pregunta = self.driver.execute_script(JS_EXTRACTION_SCRIPT)
                
                if 'error' in datos_pregunta or datos_pregunta.get('pregunta') == 'N/D':
                    self.log(f"Fin o Error: {datos_pregunta.get('detalle', 'Fin del test.')}")
                    break

                pregunta_id = datos_pregunta.get('id_pregunta', 'N/A')
                
                if pregunta_id not in [r.get('id_pregunta') for r in resultados if isinstance(r, dict)]:
                    
                    pregunta_formateada = {
                        "pregunta": datos_pregunta["pregunta"],
                        "opciones": datos_pregunta["opciones"],
                        "respuesta": datos_pregunta["respuesta"]
                    }
                    
                    pregunta_control = pregunta_formateada.copy()
                    pregunta_control['id_pregunta'] = pregunta_id 
                    
                    resultados.append(pregunta_control)
                    
                    current_count = len(resultados)
                    progress_value = current_count / self.total_questions
                    self.after(0, lambda: self.progress_bar.set(progress_value))
                    
                    self.log(f"Pregunta {len(resultados)}/{self.total_questions}: {datos_pregunta['pregunta']}.\nRespuesta: {pregunta_formateada['respuesta'][0]}\n")
                    
                    resultados_final = [{k: v for k, v in res.items() if k not in ['id_pregunta', 'cadena_marcadores']} for res in resultados]
                    with open(self.file_name, 'w', encoding='utf-8') as f:
                        json.dump(resultados_final, f, indent=4, ensure_ascii=False)
                
                try:
                    self.driver.execute_script("contestar(0)")
                    time.sleep(0.25) 
                    
                    boton = self.driver.find_element(By.ID, "boton")
                    boton.click()
                    time.sleep(0.25) 

                except Exception:
                    self.log("No se pudo hacer clic en 'Siguiente'. Finalizando.")
                    break

        except WebDriverException as e:
            self.log(f"ERROR: Fallo de Selenium. Verifique el driver y la URL. Detalle: {e}")
            
        except Exception as e:
            self.log(f"ERROR: {e}")
            
        finally:
            self.after(0, lambda: self.progress_bar.set(1.0))
            self.stop_scraping()

if __name__ == "__main__":
    app = ScraperApp()
    app.mainloop()