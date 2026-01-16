# src/gui.py
"""ITV Station Search GUI with ttkbootstrap and OpenStreetMap integration."""
import threading
import time

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
    
    # Marker colors
    MARKER_COLOR_NORMAL = ("#C02720", "#EA4335")       # Red (circle, outside)
    MARKER_COLOR_HIGHLIGHT = ("#FF6600", "#FF8C00")    # Orange (circle, outside)

    def __init__(self):
        """Initialize the application."""
        self.root = ttk.Window(
            title="Buscador de Estaciones ITV",
            themename="solar",
            size=(1400, 850),
            minsize=(1200, 700)
        )
        self.root.position_center()

        # Store all markers with their station data for recreation
        self.all_markers = {}  # {station_id: marker}
        self.station_data = {}  # {station_id: station_dict} for marker recreation
        
        # Store current search result IDs for highlighting
        self.search_result_ids = set()
        
        # Info popup reference
        self.info_popup = None
        self.popup_show_time = 0  # Timestamp when popup was shown
        
        # Flag to skip zoom when selection is from marker click
        self._skip_zoom_on_select = False
        
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
        
        # Right side controls frame
        right_controls = ttk.Frame(header_frame)
        right_controls.pack(side=RIGHT)
        
        # Refresh button
        self.refresh_btn = ttk.Button(
            right_controls,
            text="Refrescar",
            command=self._refresh_data,
            bootstyle="warning-outline",
            width=12
        )
        self.refresh_btn.pack(side=RIGHT, padx=(10, 0))
        
        # Theme selector
        theme_frame = ttk.Frame(right_controls)
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
        
        # Bind click on map to hide popup
        self.map_widget.canvas.bind("<Button-1>", self._on_map_click, add="+")

        
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
        """Handle loaded stations - populate dropdowns and map with all markers."""
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
        
        # Clear old markers and create new ones for all stations
        self._clear_all_markers()
        self._create_all_markers()
        
        # Display all stations in table (not filtered, so all markers stay red)
        self._display_results(data, is_filtered=False)
    
    def _create_all_markers(self, highlight_ids=None):
        """Create markers for all stations on the map.
        
        Args:
            highlight_ids: Set of station IDs to highlight in orange. If None, all are red.
        """
        highlight_ids = highlight_ids or set()
        
        # Helper function to create a marker
        def create_marker(est, is_highlighted):
            lat = est.get('latitud')
            lon = est.get('longitud')
            station_id = est.get('nombre')
            
            if not (lat and lon and station_id):
                return
            
            # Store station data for later recreation
            self.station_data[station_id] = est
            
            # Determine color
            if is_highlighted:
                color_circle = self.MARKER_COLOR_HIGHLIGHT[0]
                color_outside = self.MARKER_COLOR_HIGHLIGHT[1]
            else:
                color_circle = self.MARKER_COLOR_NORMAL[0]
                color_outside = self.MARKER_COLOR_NORMAL[1]
            
            # Create closure to capture est value
            def make_click_handler(station):
                def handler(marker):
                    self._on_marker_click(station)
                return handler
            
            marker = self.map_widget.set_marker(
                lat, lon,
                text="",
                marker_color_circle=color_circle,
                marker_color_outside=color_outside,
                command=make_click_handler(est)
            )
            self.all_markers[station_id] = marker
        
        # First pass: create non-highlighted markers (red) - these go on bottom
        for est in self.all_stations:
            station_id = est.get('nombre')
            if station_id and station_id not in highlight_ids:
                create_marker(est, is_highlighted=False)
        
        # Second pass: create highlighted markers (orange) - these go on top
        for est in self.all_stations:
            station_id = est.get('nombre')
            if station_id and station_id in highlight_ids:
                create_marker(est, is_highlighted=True)
    
    def _refresh_data(self):
        """Refresh all data from the API."""
        self.refresh_btn.configure(text="Cargando...", state="disabled")
        threading.Thread(target=self._fetch_and_refresh, daemon=True).start()
    
    def _fetch_and_refresh(self):
        """Fetch data and refresh the UI."""
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/estaciones",
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                self.root.after(0, lambda: self._on_refresh_complete(data))
            else:
                self.root.after(0, lambda: self._on_refresh_error())
                
        except Exception:
            self.root.after(0, lambda: self._on_refresh_error())
    
    def _on_refresh_complete(self, data):
        """Handle refresh completion."""
        self._on_stations_loaded(data)
        self.refresh_btn.configure(text="Refrescar", state="normal")
        self._clear_search()
    
    def _on_refresh_error(self):
        """Handle refresh error."""
        self.refresh_btn.configure(text="Refrescar", state="normal")
        
    def _clear_search(self):
        """Clear all search fields and show all stations."""
        self.localidad_var.set("")
        self.codigo_postal_var.set("")
        self.provincia_var.set("")
        self.tipo_var.set("Todos")
        
        # Reset all marker colors to normal (red)
        self._reset_marker_colors()
        
        # Reload all stations in table (not filtered, so all markers stay red)
        if self.all_stations:
            self._display_results({'resultados': self.all_stations, 'total': len(self.all_stations)}, is_filtered=False)
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
        
        # Check if any filters are applied
        has_filters = len(params) > 0
        
        # Perform API call in background thread
        threading.Thread(target=self._api_search, args=(params, has_filters), daemon=True).start()
        
    def _api_search(self, params, has_filters):
        """Make API request for search."""
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/estaciones",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                # Only highlight markers if actual filters were applied
                self.root.after(0, lambda: self._display_results(data, is_filtered=has_filters))
            elif response.status_code == 404:
                self.root.after(0, lambda: self._display_no_results())
                
        except Exception:
            pass
            
    def _display_results(self, data, fit_to_results=False, is_filtered=False):
        """Display search results in table and optionally highlight markers.
        
        Args:
            data: Response data with 'resultados' and 'total'
            fit_to_results: Whether to zoom map to show results
            is_filtered: If True, highlight matching markers in orange. If False, keep all red.
        """
        self.results = data.get('resultados', [])
        total = data.get('total', 0)
        
        # Get IDs of search results
        self.search_result_ids = set()
        for est in self.results:
            station_id = est.get('nombre')
            if station_id:
                self.search_result_ids.add(station_id)
        
        # Update results label
        self.results_label.configure(
            text=f"Resultados de búsqueda: {total} encontrados"
        )
        
        # Clear existing table data
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Only highlight markers if this is a filtered search
        if is_filtered:
            self._highlight_markers()
        else:
            self._reset_marker_colors()
        
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
        
        # Fit map to show highlighted markers only if explicitly requested
        if fit_to_results and self.search_result_ids:
            self._fit_to_results()
        
    def _display_no_results(self):
        """Display no results message."""
        self.results = []
        self.search_result_ids = set()
        for item in self.tree.get_children():
            self.tree.delete(item)
        # Reset all marker colors to red (no highlights)
        self._reset_marker_colors()
        self.results_label.configure(
            text="Resultados de búsqueda: 0 encontrados"
        )
    
    def _highlight_markers(self):
        """Highlight markers that match search results (orange), reset others (red)."""
        # Delete all existing markers and recreate with correct colors
        self._clear_all_markers()
        self._create_all_markers(highlight_ids=self.search_result_ids)
    
    def _reset_marker_colors(self):
        """Reset all markers to normal color (red)."""
        self.search_result_ids = set()
        # Delete all existing markers and recreate in red
        self._clear_all_markers()
        self._create_all_markers(highlight_ids=None)
    
    def _clear_all_markers(self):
        """Remove all markers from the map."""
        for station_id, marker in self.all_markers.items():
            marker.delete()
        self.all_markers = {}
        
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
        # Skip zoom if selection was triggered by marker click
        if self._skip_zoom_on_select:
            self._skip_zoom_on_select = False
            return
        
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
                    self.map_widget.set_zoom(10)
                break
    
    def _on_marker_click(self, station):
        """Handle marker click - show info popup and highlight row in table."""
        nombre = station.get('nombre')
        if not nombre:
            return
        
        # Show info popup
        self._show_info_popup(station)
        
        # Set flag to skip zoom when selecting in table
        self._skip_zoom_on_select = True
        
        # Find and select the corresponding row in the table
        for item_id in self.tree.get_children():
            item = self.tree.item(item_id)
            if item['values'] and item['values'][0] == nombre:
                # Select and scroll to the row
                self.tree.selection_set(item_id)
                self.tree.see(item_id)
                self.tree.focus(item_id)
                break
    
    def _show_info_popup(self, station):
        """Show info popup for a station."""
        # Hide existing popup first
        self._hide_info_popup()
        
        lat = station.get('latitud')
        lon = station.get('longitud')
        if not lat or not lon:
            return
        
        # Get station info
        nombre = station.get('nombre', 'N/A')
        tipo = station.get('tipo', 'N/A')
        direccion = station.get('direccion') or 'N/A'
        localidad = station.get('localidad_nombre') or 'N/A'
        provincia = station.get('provincia_nombre') or 'N/A'
        cod_postal = station.get('codigo_postal') or 'N/A'
        horario = station.get('horario') or 'N/A'
        
        # Build info text
        info_text = f"""{nombre}

Tipo: {tipo}
Dirección: {direccion}
Localidad: {localidad}
Provincia: {provincia}
Cód. Postal: {cod_postal}
Horario: {horario}"""
        
        # Create popup frame on the map canvas
        self.info_popup = ttk.Frame(self.map_widget, bootstyle="warning")
        
        # Create label with info
        info_label = ttk.Label(
            self.info_popup,
            text=info_text,
            font=("Segoe UI", 9),
            padding=10,
            justify="left",
            wraplength=250,
            bootstyle="inverse-warning"
        )
        info_label.pack(fill=BOTH, expand=True)
        
        # Close button
        close_btn = ttk.Button(
            self.info_popup,
            text="✕ Cerrar",
            command=self._hide_info_popup,
            bootstyle="warning-outline",
            width=10
        )
        close_btn.pack(pady=(0, 5))
        
        # Position popup near the marker (offset to not cover it)
        # Get canvas position of the lat/lon
        x, y = self.map_widget.canvas.winfo_width() // 2, self.map_widget.canvas.winfo_height() // 2
        
        # Place popup on canvas
        self.info_popup.place(x=x + 20, y=y - 100, anchor="w")
        
        # Record time popup was shown
        self.popup_show_time = time.time()
    
    def _hide_info_popup(self, event=None):
        """Hide the info popup."""
        if self.info_popup:
            self.info_popup.destroy()
            self.info_popup = None
    
    def _on_map_click(self, event):
        """Handle click on map - hide popup if it's been open for a while."""
        # Ignore clicks within 500ms of showing popup (to avoid instant close)
        if time.time() - self.popup_show_time < 0.5:
            return
        self._hide_info_popup()
                
    def run(self):
        """Run the application."""
        self.root.mainloop()


def main():
    """Entry point for the GUI application."""
    app = ITVSearchApp()
    app.run()


if __name__ == "__main__":
    main()
