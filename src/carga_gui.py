import tkinter as tk

class CargaApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Carga de datos")
        self.root.geometry("500x300")

        tk.Label(
            self.root,
            text="Pantalla de carga",
            font=("Arial", 16)
        ).pack(pady=40)

    def run(self):
        self.root.mainloop()
