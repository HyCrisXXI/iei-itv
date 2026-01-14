import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import BooleanVar, Text, DISABLED, NORMAL, END

class ITVCargaApp(ttk.Frame):
    FUENTES = [
        ("Galicia", "galicia"),
        ("Comunitat Valenciana", "cv"),
        ("Catalunya", "cat"),
    ]

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
        self._set_resultados(
            "Número de registros cargados correctamente:\n"
            "Registros con errores y reparados:\n"
            "Registros con errores y rechazados:\n"
        )

    def _borrar(self):
        self._set_resultados("Almacén de datos borrado.")

    def _set_resultados(self, text):
        self.resultados.config(state=NORMAL)
        self.resultados.delete(1.0, END)
        self.resultados.insert(END, text)
        self.resultados.config(state=DISABLED)

    def run(self):
        if self._own_window:
            self.master.mainloop()

if __name__ == "__main__":
    ITVCargaApp().run()
