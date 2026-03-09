import json
import threading
import time
from tkinter import filedialog

import customtkinter as ctk
from selenium import webdriver
from selenium.webdriver.common.by import By


class DaypoAutoSolver(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("daypo resolver")
        self.geometry("500x450")
        self.driver = None
        self.is_running = False

        ctk.CTkLabel(self, text="configuración", font=("Arial", 16, "bold")).pack(
            pady=10
        )
        self.url_entry = ctk.CTkEntry(self, width=400, placeholder_text="url del test")
        self.url_entry.pack(pady=5)

        self.file_entry = ctk.CTkEntry(
            self, width=400, placeholder_text="ruta del json"
        )
        self.file_entry.pack(pady=5)

        self.btn_file = ctk.CTkButton(
            self, text="seleccionar archivo", command=self.browse_file
        )
        self.btn_file.pack(pady=5)

        self.btn_start = ctk.CTkButton(self, text="iniciar", command=self.start_thread)
        self.btn_start.pack(pady=20)

        self.status_label = ctk.CTkLabel(
            self, text="estado: esperando", text_color="gray"
        )
        self.status_label.pack(pady=5)

        self.log_view = ctk.CTkTextbox(self, width=450, height=150, state="disabled")
        self.log_view.pack(pady=10)

    def browse_file(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if filename:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, filename)

    def log(self, msg):
        self.after(
            0,
            lambda: (
                self.log_view.configure(state="normal"),
                self.log_view.insert("end", f"{msg}\n"),
                self.log_view.see("end"),
                self.log_view.configure(state="disabled"),
            ),
        )

    def start_thread(self):
        if not self.is_running:
            threading.Thread(target=self.logic, daemon=True).start()

    def logic(self):
        try:
            with open(self.file_entry.get(), "r", encoding="utf-8") as f:
                data = json.load(f)
            self.driver = webdriver.Chrome()
            self.driver.get(self.url_entry.get() or "https://www.daypo.com")
            self.is_running = True
            self.status_label.configure(text="estado: en curso", text_color="green")
            self.log("iniciado. hacé login.")

            while self.is_running:
                try:
                    if self.driver.execute_script("return typeof m !== 'undefined'"):
                        self.log("test detectado.")
                        self.solve_loop(data)
                        break
                except:
                    pass
                time.sleep(0.5)
        except Exception as e:
            self.log(f"error: {e}")
            self.is_running = False

    def solve_loop(self, data):
        while self.is_running:
            try:
                m_id = self.driver.execute_script("return m")
                pregunta_el = self.driver.find_element(By.ID, f"pri{m_id}")
                texto = pregunta_el.text.strip()
                match = next((item for item in data if item["pregunta"] == texto), None)

                if match:
                    for fila in self.driver.find_elements(
                        By.CSS_SELECTOR, f"#cuestiones{m_id} tr"
                    ):
                        tds = fila.find_elements(By.TAG_NAME, "td")
                        if len(tds) >= 3 and tds[2].text.strip() in match["respuesta"]:
                            tds[1].click()
                            time.sleep(0.01)
                    time.sleep(0.01)
                    self.driver.find_element(By.ID, "boton").click()
                    time.sleep(0.01)
                else:
                    time.sleep(0.5)
            except:
                time.sleep(1)


if __name__ == "__main__":
    app = DaypoAutoSolver()
    app.mainloop()
