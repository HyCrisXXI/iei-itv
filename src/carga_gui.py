import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import BooleanVar, Text, DISABLED, NORMAL, END, messagebox
import requests
import threading
from typing import Dict

class ITVCargaApp(ttk.Frame):
    FUENTES = [
        ("Galicia", "gal"),
        ("Comunitat Valenciana", "cv"),
        ("Catalunya", "cat"),
    ]

    LOAD_API_PORT = 8004

    def __init__(self, master=None, on_back=None, *args, **kwargs):
        # Si no hay master, crea ventana propia con el mismo tema que el buscador
        if master is None:
            self._own_window = True
            master = ttk.Window(
                themename="solar",
                title="Carga de datos",
                size=(700, 500),
                minsize=(600, 400)
            )
            master.position_center()
        else:
            self._own_window = False
        super().__init__(master, *args, **kwargs)
        self.master = master
        self.on_back = on_back
        self.pack(fill=BOTH, expand=True)
        self.selected_fuentes = {key: BooleanVar(value=False) for _, key in self.FUENTES}
        self.select_all_var = BooleanVar(value=False)
        self._build_ui()

    def _build_ui(self):
        # Obtener color de fondo principal del tema
        bg_color = self.master.style.colors.bg  # ttkbootstrap color

        # Fondo uniforme
        self.configure(style="TFrame")
        self.master.configure(bg=bg_color)
        self["padding"] = 0

        # Header
        header = ttk.Frame(self, padding=(10, 10, 10, 0), style="TFrame")
        header.pack(fill=X)
        header.configure(style="TFrame")
        ttk.Label(
            header,
            text="Carga del almacén de datos",
            font=("Segoe UI", 20, "bold"),
            bootstyle="warning"
        ).pack(side=LEFT)
        ttk.Button(header, text="Volver", width=6, bootstyle="secondary-outline", command=self._back).pack(side=RIGHT, padx=(0, 5))

        # Main content
        main = ttk.Frame(self, style="TFrame")
        main.pack(expand=True, fill=BOTH, pady=(30, 0))
        main.configure(style="TFrame")

        # Selección de fuente (centrado)
        fuente_frame = ttk.Frame(main, style="TFrame")
        fuente_frame.pack(pady=(0, 20))
        fuente_frame.configure(style="TFrame")
        ttk.Label(fuente_frame, text="Seleccione fuente:", font=("Segoe UI", 12, "bold"), bootstyle="warning").grid(row=0, column=0, sticky=W, columnspan=2, pady=(0, 10))
        ttk.Checkbutton(
            fuente_frame, text="Seleccionar todas", variable=self.select_all_var,
            command=self._toggle_all, bootstyle="checkbox"
        ).grid(row=1, column=0, sticky=W, columnspan=2, pady=2)
        for i, (label, key) in enumerate(self.FUENTES, start=2):
            ttk.Checkbutton(
                fuente_frame, text=label, variable=self.selected_fuentes[key],
                command=self._update_select_all, bootstyle="checkbox"
            ).grid(row=i, column=0, sticky=W, columnspan=2, pady=2)

        # Botones (centrados)
        btn_frame = ttk.Frame(main, style="TFrame")
        btn_frame.pack(pady=(10, 20))
        btn_frame.configure(style="TFrame")
        ttk.Button(btn_frame, text="Cancelar", width=12, bootstyle="secondary-outline", command=self._reset).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Cargar", width=12, bootstyle="warning", command=self._cargar).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Borrar almacén de datos", width=24, bootstyle="danger", command=self._borrar).pack(side=LEFT, padx=5)

        # Resultados
        resultados_label = ttk.Label(main, text="Resultados de la carga:", font=("Segoe UI", 12, "bold"), bootstyle="warning")
        resultados_label.pack(anchor=W, pady=(10, 0))
        self.resultados = Text(main, height=8, width=60, font=("Consolas", 10), state=DISABLED, wrap="word", borderwidth=1, relief="solid", bg=bg_color, fg="#fff")
        self.resultados.pack(pady=(5, 0), fill=X)

    def _toggle_all(self):
        val = self.select_all_var.get()
        for var in self.selected_fuentes.values():
            var.set(val)

    def _update_select_all(self):
        all_selected = all(var.get() for var in self.selected_fuentes.values())
        self.select_all_var.set(all_selected)

    def _reset(self):
        self.select_all_var.set(False)
        for var in self.selected_fuentes.values():
            var.set(False)
        self._set_resultados("")

    def _back(self):
        if self.on_back:
            self.on_back()
        elif self._own_window:
            self.master.destroy()

    def _cargar(self):
        # Validar que se seleccione al menos una fuente
        seleccionadas = [key for key, var in self.selected_fuentes.items() if var.get()]
        if not seleccionadas:
            messagebox.showwarning("Advertencia", "Selecciona al menos una fuente de datos")
            return
        
        # Iniciar carga en hilo separado para no bloquear la GUI
        self._set_resultados("Cargando datos...\n\nEspera por favor...")
        threading.Thread(target=self._cargar_datos, args=(seleccionadas,), daemon=True).start()
    
    def _cargar_datos(self, fuentes: list):
        """Realiza la carga de datos invocando únicamente a la API de carga."""
        try:
            self._agregar_resultado(f"\n▶ Ejecutando carga para: {', '.join(f.upper() for f in fuentes)}")
            url = f"http://localhost:{self.LOAD_API_PORT}/load/run"
            payload = {"fuentes": fuentes}
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            self._mostrar_resumen_carga(data)
        except requests.exceptions.ConnectionError:
            msg = "✗ Error: No se puede conectar a la API de carga. Asegúrate de que está ejecutándose."
            self._agregar_resultado(f"\n{msg}")
            messagebox.showerror("Error", msg)
        except requests.exceptions.HTTPError as exc:
            detail = self._extraer_error_response(exc)
            self._agregar_resultado(f"\n✗ Error en la API de carga: {detail}")
            messagebox.showerror("Error", f"API de carga: {detail}")
        except Exception as e:
            self._agregar_resultado(f"\n✗ Error general: {str(e)}")
    
    def _extraer_error_response(self, exc: requests.exceptions.HTTPError) -> str:
        try:
            data = exc.response.json()
            detail = data.get("detail")
            if isinstance(detail, list):
                return "; ".join(str(item) for item in detail)
            if detail:
                return str(detail)
        except Exception:  # pylint: disable=broad-except
            pass
        return str(exc)

    def _mostrar_resumen_carga(self, data: Dict):
        total_insertados = data.get("total_insertados", 0)
        self._agregar_resultado(f"\nNúmero de registros cargados correctamente: {total_insertados}")

        self._agregar_resultado("\nRegistros con errores y reparados:")
        reparados = data.get("reparados", []) or []
        if not reparados:
            self._agregar_resultado("  Ninguno")
        else:
            for reparado in reparados:
                fuente = str(reparado.get("fuente", "-")).upper()
                nombre = reparado.get("nombre", "Desconocido")
                localidad = reparado.get("localidad", "Sin localidad")
                motivo = reparado.get("motivo", "-")
                operacion = reparado.get("operacion", "-")
                self._agregar_resultado(
                    "  {Fuente de datos: %s, Nombre: %s, Localidad: %s, Motivo del error: %s, Operación realizada: %s}" % (
                        fuente,
                        nombre,
                        localidad,
                        motivo,
                        operacion,
                    )
                )

        self._agregar_resultado("\nRegistros con errores y rechazados:")
        rechazados = data.get("rechazados", []) or []
        if not rechazados:
            self._agregar_resultado("  Ninguno")
        else:
            for rechazado in rechazados:
                fuente = str(rechazado.get("fuente", "-")).upper()
                nombre = rechazado.get("nombre", "Desconocido")
                localidad = rechazado.get("localidad", "Sin localidad")
                motivo = rechazado.get("motivo", "-")
                self._agregar_resultado(
                    "  {Fuente de datos: %s, Nombre: %s, Localidad: %s, Motivo del error: %s}" % (
                        fuente,
                        nombre,
                        localidad,
                        motivo,
                    )
                )

    def _borrar(self):
        # Confirmación
        if not messagebox.askyesno("Confirmar", "¿Estás seguro de que deseas borrar todo el almacén de datos?"):
            return
        
        self._set_resultados("Borrando almacén de datos...\nEspera por favor...")
        threading.Thread(target=self._borrar_datos, daemon=True).start()
    
    def _borrar_datos(self):
        """Borra todo el almacén de datos"""
        try:
            response = requests.delete(f"http://localhost:{self.LOAD_API_PORT}/load", timeout=30)
            response.raise_for_status()
            resultado = response.json()
            
            self._set_resultados(
                f"✓ Almacén de datos borrado correctamente\n\n"
                f"Eliminados:\n"
                f"  - Estaciones: {resultado['eliminados']['estaciones']}\n"
                f"  - Localidades: {resultado['eliminados']['localidades']}\n"
                f"  - Provincias: {resultado['eliminados']['provincias']}"
            )
            messagebox.showinfo("Éxito", "Almacén de datos borrado correctamente")
        except requests.exceptions.ConnectionError:
            self._set_resultados("✗ Error: No se puede conectar a la API de carga.\nAsegúrate de que está ejecutándose.")
            messagebox.showerror("Error", "No se puede conectar a la API de carga")
        except Exception as e:
            self._set_resultados(f"✗ Error al borrar: {str(e)}")
            messagebox.showerror("Error", f"Error al borrar: {str(e)}")

    def _set_resultados(self, text):
        self.resultados.config(state=NORMAL)
        self.resultados.delete(1.0, END)
        self.resultados.insert(END, text)
        self.resultados.config(state=DISABLED)
    
    def _agregar_resultado(self, text):
        """Agrega texto al área de resultados sin limpiar lo anterior"""
        self.resultados.config(state=NORMAL)
        self.resultados.insert(END, text + "\n")
        self.resultados.see(END)  # Scroll automático al final
        self.resultados.config(state=DISABLED)
        self.resultados.update()  # Actualizar GUI

    def run(self):
        if self._own_window:
            self.master.mainloop()

if __name__ == "__main__":
    ITVCargaApp().run()
