# src/gui.py
"""ITV Station Search GUI with ttkbootstrap and OpenStreetMap integration."""
import threading

import requests
import ttkbootstrap as ttk
import tkintermapview
from ttkbootstrap.constants import *


class ITVSearchApp:
    """Main application class for ITV Station Search."""
    
    # Available ttkbootstrap themes
    THEMES = [
        "solar", "darkly", "cyborg", "vapor", "superhero",
        "cosmo", "flatly", "journal", "litera", "lumen",
        "minty", "morph", "pulse", "sandstone", "simplex",
        "sketchy", "slate", "spacelab", "united", "yeti"
    ]
    
    # Station types from database model
    TIPOS_ESTACION = ["Todos", "Fija", "Movil", "Otros"]
    
    # API base URL
    API_BASE_URL = "http://localhost:8000"
    # Tile source URL (plain OSM)
    TILE_SERVER_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

    def __init__(self):
        """Initialize the application."""
        self.root = ttk.Window(
            title="Buscador de Estaciones ITV",
            themename="solar",
            size=(1400, 850),
            minsize=(1200, 700)
        )
        self.root.position_center()

        # Store current markers for cleanup
        self.markers = []
        
        # Store search results
        self.results = []
        
        # Store all stations for dropdowns
        self.all_stations = []
        self.all_localidades = []
        self.all_provincias = []
        
        # Build the UI
        self._create_header()
        self._create_main_content()
        self._create_results_section()
        
        # Initialize map to Spain
        self.map_widget.set_position(40.4168, -3.7038)
        self.map_widget.set_zoom(6)
        
        # Load all stations on startup
        self.root.after(100, self._load_all_stations)
        
    def _create_header(self):
        """Create the header with title and theme selector."""
        header_frame = ttk.Frame(self.root, padding=10)
        header_frame.pack(fill=X)
        
        # Title on the left
        title_label = ttk.Label(
            header_frame,
            text="Buscador de Estaciones ITV",
            font=("Segoe UI", 20, "bold"),
            bootstyle="warning"
        )
        title_label.pack(side=LEFT)
        
        # Theme selector on the right
        theme_frame = ttk.Frame(header_frame)
        theme_frame.pack(side=RIGHT)
        
        ttk.Label(
            theme_frame,
            text="Tema:",
            font=("Segoe UI", 10)
        ).pack(side=LEFT, padx=(0, 5))
        
        self.theme_var = ttk.StringVar(value="solar")
        theme_combo = ttk.Combobox(
            theme_frame,
            textvariable=self.theme_var,
            values=self.THEMES,
            state="readonly",
            width=12,
            bootstyle="warning"
        )
        theme_combo.pack(side=LEFT)
        theme_combo.bind("<<ComboboxSelected>>", self._on_theme_change)
        
    def _on_theme_change(self, event=None):
        """Handle theme change."""
        new_theme = self.theme_var.get()
        self.root.style.theme_use(new_theme)
        
    def _create_main_content(self):
        """Create the main content area with search panel and map."""
        content_frame = ttk.Frame(self.root, padding=10)
        content_frame.pack(fill=BOTH, expand=True)
        
        # Configure grid weights - map gets more space (70/30 split)
        content_frame.columnconfigure(0, weight=1, minsize=320)
        content_frame.columnconfigure(1, weight=3, minsize=600)
        content_frame.rowconfigure(0, weight=1)
        
        # Left panel - Search filters
        self._create_search_panel(content_frame)
        
        # Right panel - Map
        self._create_map_panel(content_frame)
        
    def _create_search_panel(self, parent):
        """Create the search filters panel."""
        search_frame = ttk.Labelframe(
            parent,
            text="Filtros de Búsqueda",
            padding=20,
            bootstyle="warning"
        )
        search_frame.grid(row=0, column=0, sticky=NSEW, padx=(0, 10))
        
        # Localidad (autocomplete combobox)
        ttk.Label(
            search_frame,
            text="Localidad:",
            font=("Segoe UI", 11)
        ).pack(anchor=W, pady=(0, 5))
        
        self.localidad_var = ttk.StringVar()
        self.localidad_combo = ttk.Combobox(
            search_frame,
            textvariable=self.localidad_var,
            font=("Segoe UI", 11),
            bootstyle="warning"
        )
        self.localidad_combo.pack(fill=X, pady=(0, 15))
        self.localidad_combo.bind('<KeyRelease>', self._filter_localidades)
        
        # Código Postal
        ttk.Label(
            search_frame,
            text="Cód. Postal:",
            font=("Segoe UI", 11)
        ).pack(anchor=W, pady=(0, 5))
        
        self.codigo_postal_var = ttk.StringVar()
        ttk.Entry(
            search_frame,
            textvariable=self.codigo_postal_var,
            font=("Segoe UI", 11),
            bootstyle="warning"
        ).pack(fill=X, pady=(0, 15))
        
        # Provincia (autocomplete combobox)
        ttk.Label(
            search_frame,
            text="Provincia:",
            font=("Segoe UI", 11)
        ).pack(anchor=W, pady=(0, 5))
        
        self.provincia_var = ttk.StringVar()
        self.provincia_combo = ttk.Combobox(
            search_frame,
            textvariable=self.provincia_var,
            font=("Segoe UI", 11),
            bootstyle="warning"
        )
        self.provincia_combo.pack(fill=X, pady=(0, 15))
        self.provincia_combo.bind('<KeyRelease>', self._filter_provincias)
        
        # Tipo
        ttk.Label(
            search_frame,
            text="Tipo:",
            font=("Segoe UI", 11)
        ).pack(anchor=W, pady=(0, 5))
        
        self.tipo_var = ttk.StringVar(value="Todos")
        ttk.Combobox(
            search_frame,
            textvariable=self.tipo_var,
            values=self.TIPOS_ESTACION,
            font=("Segoe UI", 11),
            state="readonly",
            bootstyle="warning"
        ).pack(fill=X, pady=(0, 25))
        
        # Buttons
        btn_frame = ttk.Frame(search_frame)
        btn_frame.pack(fill=X)
        
        ttk.Button(
            btn_frame,
            text="Cancelar",
            command=self._clear_search,
            bootstyle="secondary-outline",
            width=12
        ).pack(side=LEFT, expand=True, padx=(0, 5))
        
        ttk.Button(
            btn_frame,
            text="Buscar",
            command=self._perform_search,
            bootstyle="warning",
            width=12
        ).pack(side=RIGHT, expand=True, padx=(5, 0))
        
    def _filter_localidades(self, event=None):
        """Filter localidades dropdown based on typed text."""
        # Skip if arrow keys or navigation
        if event and event.keysym in ('Down', 'Up', 'Left', 'Right', 'Return', 'Escape'):
            return
        typed = self.localidad_var.get().lower()
        if typed:
            filtered = [l for l in self.all_localidades if typed in l.lower()]
            self.localidad_combo['values'] = filtered[:20]
        else:
            self.localidad_combo['values'] = self.all_localidades[:20]
            
    def _filter_provincias(self, event=None):
        """Filter provincias dropdown based on typed text."""
        # Skip if arrow keys or navigation
        if event and event.keysym in ('Down', 'Up', 'Left', 'Right', 'Return', 'Escape'):
            return
        typed = self.provincia_var.get().lower()
        if typed:
            filtered = [p for p in self.all_provincias if typed in p.lower()]
            self.provincia_combo['values'] = filtered
        else:
            self.provincia_combo['values'] = self.all_provincias
        
    def _create_map_panel(self, parent):
        """Create the map panel with OpenStreetMap."""
        map_frame = ttk.Labelframe(
            parent,
            text="Mapa de Estaciones",
            padding=10,
            bootstyle="warning"
        )
        map_frame.grid(row=0, column=1, sticky=NSEW)
        
        # Map widget
        self.map_widget = tkintermapview.TkinterMapView(
            map_frame,
            corner_radius=10
        )
        self.map_widget.set_tile_server(self.TILE_SERVER_URL, max_zoom=18)
        self.map_widget.pack(fill=BOTH, expand=True)
        
        # Map controls
        controls_frame = ttk.Frame(map_frame)
        controls_frame.pack(fill=X, pady=(10, 0))
        
        ttk.Button(
            controls_frame,
            text="Centrar en España",
            command=self._center_map_spain,
            bootstyle="info-outline"
        ).pack(side=LEFT)
        
        ttk.Button(
            controls_frame,
            text="Ajustar a Resultados",
            command=self._fit_to_results,
            bootstyle="info-outline"
        ).pack(side=LEFT, padx=(10, 0))

        
    def _create_results_section(self):
        """Create the results section with table."""
        results_frame = ttk.Frame(self.root, padding=10)
        results_frame.pack(fill=BOTH, expand=True)
        
        # Results header
        header_frame = ttk.Frame(results_frame)
        header_frame.pack(fill=X, pady=(0, 10))
        
        self.results_label = ttk.Label(
            header_frame,
            text="Resultados de búsqueda: 0 encontrados",
            font=("Segoe UI", 12, "bold"),
            bootstyle="warning"
        )
        self.results_label.pack(side=LEFT)
        
        # Create Treeview with scrollbars
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=BOTH, expand=True)
        
        # Columns definition (added descripcion)
        columns = ("nombre", "tipo", "direccion", "localidad", "provincia", "cod_postal", "horario", "descripcion")
        
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            bootstyle="warning"
        )
        
        # Define headings
        self.tree.heading("nombre", text="Nombre", anchor=W)
        self.tree.heading("tipo", text="Tipo", anchor=W)
        self.tree.heading("direccion", text="Dirección", anchor=W)
        self.tree.heading("localidad", text="Localidad", anchor=W)
        self.tree.heading("provincia", text="Provincia", anchor=W)
        self.tree.heading("cod_postal", text="Cód. Postal", anchor=W)
        self.tree.heading("horario", text="Horario", anchor=W)
        self.tree.heading("descripcion", text="Descripción", anchor=W)
        
        # Define column widths
        self.tree.column("nombre", width=200, minwidth=150)
        self.tree.column("tipo", width=80, minwidth=60)
        self.tree.column("direccion", width=250, minwidth=150)
        self.tree.column("localidad", width=120, minwidth=80)
        self.tree.column("provincia", width=120, minwidth=80)
        self.tree.column("cod_postal", width=90, minwidth=70)
        self.tree.column("horario", width=200, minwidth=100)
        self.tree.column("descripcion", width=300, minwidth=150)
        
        # Scrollbars
        y_scroll = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        x_scroll = ttk.Scrollbar(tree_frame, orient=HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        
        # Grid layout for tree and scrollbars
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        self.tree.grid(row=0, column=0, sticky=NSEW)
        y_scroll.grid(row=0, column=1, sticky=NS)
        x_scroll.grid(row=1, column=0, sticky=EW)
        
        # Bind row selection to map highlight
        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)
        
    def _load_all_stations(self):
        """Load all stations on startup."""
        threading.Thread(target=self._fetch_all_stations, daemon=True).start()
        
    def _fetch_all_stations(self):
        """Fetch all stations from API."""
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/estaciones",
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                self.root.after(0, lambda: self._on_stations_loaded(data))
                
        except Exception:
            pass  # Silently fail on startup
            
    def _on_stations_loaded(self, data):
        """Handle loaded stations - populate dropdowns and map."""
        self.all_stations = data.get('resultados', [])
        
        # Extract unique localidades and provincias for dropdowns
        localidades_set = set()
        provincias_set = set()
        
        for est in self.all_stations:
            loc = est.get('localidad_nombre')
            prov = est.get('provincia_nombre')
            if loc:
                localidades_set.add(loc)
            if prov:
                provincias_set.add(prov)
        
        self.all_localidades = [""] + sorted(list(localidades_set))
        self.all_provincias = [""] + sorted(list(provincias_set))
        
        # Update dropdowns
        self.localidad_combo['values'] = self.all_localidades[:20]
        self.provincia_combo['values'] = self.all_provincias
        
        # Display all stations
        self._display_results(data)
        
    def _clear_search(self):
        """Clear all search fields and show all stations."""
        self.localidad_var.set("")
        self.codigo_postal_var.set("")
        self.provincia_var.set("")
        self.tipo_var.set("Todos")
        
        # Reload all stations
        if self.all_stations:
            self._display_results({'resultados': self.all_stations, 'total': len(self.all_stations)})
            self._center_map_spain()
        
    def _perform_search(self):
        """Perform search using the API."""
        self.root.update()
        
        # Build query parameters
        params = {}
        
        localidad = self.localidad_var.get().strip()
        if localidad:
            params['localidad'] = localidad
            
        cod_postal = self.codigo_postal_var.get().strip()
        if cod_postal:
            params['cod_postal'] = cod_postal
            
        provincia = self.provincia_var.get().strip()
        if provincia:
            params['provincia'] = provincia
            
        tipo = self.tipo_var.get()
        if tipo and tipo != "Todos":
            params['tipo'] = tipo
        
        # Perform API call in background thread
        threading.Thread(target=self._api_search, args=(params,), daemon=True).start()
        
    def _api_search(self, params):
        """Make API request for search."""
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/estaciones",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.root.after(0, lambda: self._display_results(data))
            elif response.status_code == 404:
                self.root.after(0, lambda: self._display_no_results())
                
        except Exception:
            pass
            
    def _display_results(self, data, fit_to_results=False):
        """Display search results in table and map."""
        self.results = data.get('resultados', [])
        total = data.get('total', 0)
        
        # Update results label
        self.results_label.configure(
            text=f"Resultados de búsqueda: {total} encontrados"
        )
        
        # Clear existing table data
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Clear existing markers
        self._clear_markers()
        
        # Add rows to table
        for est in self.results:
            self.tree.insert("", END, values=(
                est.get('nombre', 'N/A'),
                est.get('tipo', 'N/A'),
                est.get('direccion', 'N/A') or 'N/A',
                est.get('localidad_nombre', 'N/A') or 'N/A',
                est.get('provincia_nombre', 'N/A') or 'N/A',
                est.get('codigo_postal', 'N/A') or 'N/A',
                est.get('horario', 'N/A') or 'N/A',
                est.get('descripcion', 'N/A') or 'N/A',
            ))
        
        # Add markers to map with click handlers
        for idx, est in enumerate(self.results):
            lat = est.get('latitud')
            lon = est.get('longitud')
            if lat and lon:
                # Create closure to capture est value
                def make_click_handler(station):
                    def handler(marker):
                        self._on_marker_click(station)
                    return handler
                
                marker = self.map_widget.set_marker(
                    lat, lon,
                    text="",
                    marker_color_circle="#C02720",
                    marker_color_outside="#EA4335",
                    command=make_click_handler(est)
                )
                self.markers.append(marker)
        
        # Fit map to show all markers only if explicitly requested
        if fit_to_results and self.markers:
            self._fit_to_results()
        
    def _display_no_results(self):
        """Display no results message."""
        self.results = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._clear_markers()
        self.results_label.configure(
            text="Resultados de búsqueda: 0 encontrados"
        )
        
    def _clear_markers(self):
        """Remove all markers from the map."""
        for marker in self.markers:
            marker.delete()
        self.markers = []
        
    def _center_map_spain(self):
        """Center the map on Spain."""
        self.map_widget.set_position(40.4168, -3.7038)
        self.map_widget.set_zoom(6)
        
    def _fit_to_results(self):
        """Fit the map to show all result markers."""
        if not self.results:
            return
            
        # Get all coordinates
        coords = []
        for est in self.results:
            lat = est.get('latitud')
            lon = est.get('longitud')
            if lat and lon:
                coords.append((lat, lon))
                
        if not coords:
            return
            
        if len(coords) == 1:
            self.map_widget.set_position(coords[0][0], coords[0][1])
            self.map_widget.set_zoom(14)
        else:
            min_lat = min(c[0] for c in coords)
            max_lat = max(c[0] for c in coords)
            min_lon = min(c[1] for c in coords)
            max_lon = max(c[1] for c in coords)
            
            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2
            
            self.map_widget.set_position(center_lat, center_lon)
            
            lat_span = max_lat - min_lat
            lon_span = max_lon - min_lon
            max_span = max(lat_span, lon_span)
            
            if max_span > 5:
                zoom = 6
            elif max_span > 2:
                zoom = 7
            elif max_span > 1:
                zoom = 8
            elif max_span > 0.5:
                zoom = 9
            else:
                zoom = 10
                
            self.map_widget.set_zoom(zoom)
            
    def _on_row_select(self, event):
        """Handle row selection in the table."""
        selection = self.tree.selection()
        if not selection:
            return
            
        item = self.tree.item(selection[0])
        nombre = item['values'][0] if item['values'] else None
        
        if not nombre:
            return
            
        # Find the station and center map on it
        for est in self.results:
            if est.get('nombre') == nombre:
                lat = est.get('latitud')
                lon = est.get('longitud')
                if lat and lon:
                    self.map_widget.set_position(lat, lon)
                    self.map_widget.set_zoom(14)
                break
    
    def _on_marker_click(self, station):
        """Handle marker click - highlight corresponding row in table."""
        nombre = station.get('nombre')
        if not nombre:
            return
        
        # Find and select the corresponding row in the table
        for item_id in self.tree.get_children():
            item = self.tree.item(item_id)
            if item['values'] and item['values'][0] == nombre:
                # Select and scroll to the row
                self.tree.selection_set(item_id)
                self.tree.see(item_id)
                self.tree.focus(item_id)
                break
                
    def run(self):
        """Run the application."""
        self.root.mainloop()


def main():
    """Entry point for the GUI application."""
    app = ITVSearchApp()
    app.run()


if __name__ == "__main__":
    main()
