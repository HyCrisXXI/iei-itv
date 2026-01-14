import tkinter as tk
from tkinter import messagebox
from src.busqueda_gui import ITVSearchApp
from src.carga_gui import CargaApp

# Funciones de los botones
def abrir_buscador():
    root.destroy()
    ITVSearchApp().run()

def abrir_carga():
    root.destroy()
    CargaApp().run()

root = tk.Tk()
root.title("Menú principal")
root.geometry("300x200")
root.resizable(False, False)

frame = tk.Frame(root)
frame.pack(expand=True)

# Botón Buscador
btn_buscador = tk.Button(
    frame,
    text="Buscador",
    width=15,
    height=2,
    command=abrir_buscador
)
btn_buscador.pack(pady=10)

# Botón Carga
btn_carga = tk.Button(
    frame,
    text="Carga",
    width=15,
    height=2,
    command=abrir_carga
)
btn_carga.pack(pady=10)

# Ejecutar aplicación
root.mainloop()
