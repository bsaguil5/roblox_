import streamlit as st
from openai import OpenAI
import streamlit.components.v1 as components
import requests
from PIL import Image, ImageStat
import io
import os

# --- Configuration ---
TEMPLATE_URL = "https://github.com/Antosser/Roblox-Shirt-Template/blob/master/template.png?raw=true"
TEMPLATE_FILENAME = "shirt_overlay.png"
ROBLOX_WIDTH = 585
ROBLOX_HEIGHT = 559

# Logo placement coordinates (center of front torso)
LOGO_X = 231
LOGO_Y = 74
LOGO_SIZE = 128

# Pattern tile size
PATTERN_SIZE = 150

# --- Helper Functions ---

def download_template():
    """Downloads the Roblox shirt template overlay."""
    if not os.path.exists(TEMPLATE_FILENAME):
        try:
            with st.spinner("Downloading Roblox shirt template..."):
                response = requests.get(TEMPLATE_URL, timeout=15)
                response.raise_for_status()
                with open(TEMPLATE_FILENAME, "wb") as f:
                    f.write(response.content)
                st.success("Template downloaded!")
        except Exception as e:
            st.error(f"Failed to download template: {e}")
            st.info("Creating a transparent placeholder template...")
            # Create a fully transparent placeholder
            placeholder = Image.new("RGBA", (ROBLOX_WIDTH, ROBLOX_HEIGHT), (0, 0, 0, 0))
            placeholder.save(TEMPLATE_FILENAME)

def get_openai_client():
    """Initializes the OpenAI client."""
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
        if not api_key:
            st.error("OpenAI API Key not found in .streamlit/secrets.toml")
            st.stop()
        return OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"Error initializing OpenAI: {e}")
        st.stop()

def generate_image(client, prompt):
    """Generates an image using DALL-E 3."""
    try:
        with st.spinner("🎨 Generating with DALL-E 3..."):
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            img_url = response.data[0].url
            img_response = requests.get(img_url)
            img_response.raise_for_status()
            return Image.open(io.BytesIO(img_response.content)).convert("RGBA")
    except Exception as e:
        st.error(f"Image generation failed: {e}")
        return None

def get_average_color(image):
    """Calculates the average/dominant color of an image."""
    # Convert to RGB for stats calculation
    rgb_image = image.convert("RGB")
    stat = ImageStat.Stat(rgb_image)
    # Get average of each channel
    avg_color = tuple(int(c) for c in stat.mean[:3])
    return avg_color

def create_logo_mode_image(ai_image):
    """Creates shirt with centered logo and background matching dominant color."""
    # Resize AI image to logo size
    logo = ai_image.resize((LOGO_SIZE, LOGO_SIZE), Image.Resampling.LANCZOS)
    
    # Get average color from the logo
    avg_color = get_average_color(logo)
    
    # Create base image filled with average color
    base = Image.new("RGBA", (ROBLOX_WIDTH, ROBLOX_HEIGHT), (*avg_color, 255))
    
    # Paste logo at specified coordinates
    base.paste(logo, (LOGO_X, LOGO_Y), mask=logo)
    
    return base

def create_pattern_mode_image(ai_image):
    """Creates shirt with tiled pattern."""
    # Resize AI image to tile size
    tile = ai_image.resize((PATTERN_SIZE, PATTERN_SIZE), Image.Resampling.LANCZOS)
    
    # Create base image
    base = Image.new("RGBA", (ROBLOX_WIDTH, ROBLOX_HEIGHT))
    
    # Tile the pattern across the base
    for x in range(0, ROBLOX_WIDTH, PATTERN_SIZE):
        for y in range(0, ROBLOX_HEIGHT, PATTERN_SIZE):
            base.paste(tile, (x, y))
    
    return base

def apply_template_overlay(base_image):
    """Applies the shirt template overlay on top of the base image."""
    try:
        overlay = Image.open(TEMPLATE_FILENAME).convert("RGBA")
        
        # Ensure overlay matches dimensions
        if overlay.size != (ROBLOX_WIDTH, ROBLOX_HEIGHT):
            overlay = overlay.resize((ROBLOX_WIDTH, ROBLOX_HEIGHT), Image.Resampling.LANCZOS)
        
        # Composite: overlay on top of base (transparent areas show base through)
        final = Image.alpha_composite(base_image, overlay)
        
        return final
    except Exception as e:
        st.warning(f"Could not apply overlay: {e}")
        return base_image

# --- Main App ---

def get_editor_html():
    """
    HTML/JS component for the Manual Editor with Full Body 3D Preview.
    
    APPROACH: Dual Canvas Architecture
    - TWO separate Fabric.js canvases (shirtCanvas, pantsCanvas) exist simultaneously
    - Only ONE is visible/editable at a time (the other is hidden)
    - 3D preview ALWAYS reads from BOTH canvases
    - No state save/restore needed - canvases persist independently
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/fabric.js/5.3.1/fabric.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <script src="https://unpkg.com/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
        <style>
            body { margin: 0; padding: 10px; font-family: sans-serif; background-color: #0e1117; color: white; }
            .main-container { display: flex; flex-direction: column; gap: 15px; }
            .mode-toggle { 
                display: flex; 
                justify-content: center; 
                gap: 0; 
                background: #1a1a2e; 
                padding: 4px; 
                border-radius: 8px; 
                width: fit-content; 
                margin: 0 auto;
            }
            .mode-toggle label {
                padding: 10px 24px;
                cursor: pointer;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .mode-toggle input[type="radio"] { display: none; }
            .mode-toggle input[type="radio"]:checked + label {
                background: linear-gradient(135deg, #ff4b4b, #ff6b6b);
                box-shadow: 0 2px 8px rgba(255, 75, 75, 0.4);
            }
            .mode-toggle label:hover:not(:has(input:checked)) {
                background: #262730;
            }
            .controls { display: flex; gap: 8px; flex-wrap: wrap; background: #262730; padding: 12px; border-radius: 8px; justify-content: center; }
            button { padding: 8px 14px; background: #ff4b4b; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 13px; }
            button:hover { background: #ff3333; }
            button.secondary { background: #4a4a5a; }
            button.secondary:hover { background: #5a5a6a; }
            button.download-shirt { background: #2196F3; }
            button.download-shirt:hover { background: #1976D2; }
            button.download-pants { background: #9C27B0; }
            button.download-pants:hover { background: #7B1FA2; }
            button.delete { background: #f44336; }
            button.delete:hover { background: #d32f2f; }
            input[type="file"] { color: white; padding: 8px; }
            .preview-container { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; align-items: flex-start; }
            .panel { display: flex; flex-direction: column; align-items: center; gap: 8px; }
            .panel h3 { margin: 0; font-size: 16px; color: #ccc; }
            #three-container { width: 400px; height: 520px; border: 2px solid #444; background: #1a1a1a; border-radius: 4px; }
            .info { font-size: 12px; color: #888; text-align: center; max-width: 500px; }
            .legend { display: flex; gap: 15px; flex-wrap: wrap; justify-content: center; font-size: 11px; margin-top: 5px; }
            .legend-item { display: flex; align-items: center; gap: 4px; }
            .legend-color { width: 12px; height: 12px; border-radius: 2px; }
            .mode-indicator {
                text-align: center;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            .mode-indicator.shirt { background: rgba(33, 150, 243, 0.2); color: #64B5F6; }
            .mode-indicator.pants { background: rgba(156, 39, 176, 0.2); color: #CE93D8; }
            
            /* Canvas container for stacking */
            .canvas-stack {
                position: relative;
                width: 585px;
                height: 559px;
                border: 2px solid #444;
                border-radius: 4px;
            }
            .canvas-stack .canvas-container {
                position: absolute !important;
                top: 0;
                left: 0;
            }
            .canvas-stack .hidden-canvas {
                visibility: hidden;
                pointer-events: none;
            }
            .torso-only { transition: opacity 0.2s; }
            .torso-only.hidden { opacity: 0.3; pointer-events: none; }
        </style>
    </head>
    <body>
        <div class="main-container">
            <!-- Mode Toggle -->
            <div class="mode-toggle">
                <input type="radio" name="editMode" id="mode-shirt" value="shirt" checked>
                <label for="mode-shirt">👔 Editing: Shirt</label>
                <input type="radio" name="editMode" id="mode-pants" value="pants">
                <label for="mode-pants">👖 Editing: Pants</label>
            </div>
            
            <div class="controls">
                <input type="file" id="img-upload" accept="image/*">
                <button onclick="deleteSelected()" class="delete">🗑️ Delete</button>
                <button id="btn-front" onclick="fitToZone('front')" class="torso-only">Fit Front Torso</button>
                <button id="btn-back" onclick="fitToZone('back')" class="torso-only">Fit Back Torso</button>
                <button onclick="fitToZone('r_arm')" class="secondary">Fit R. Arm/Leg</button>
                <button onclick="fitToZone('l_arm')" class="secondary">Fit L. Arm/Leg</button>
                <button onclick="downloadTexture('shirt')" class="download-shirt">📥 Download Shirt</button>
                <button onclick="downloadTexture('pants')" class="download-pants">📥 Download Pants</button>
            </div>
            
            <div class="preview-container">
                <div class="panel">
                    <h3>2D Canvas (585x600)</h3>
                    <div id="mode-label" class="mode-indicator shirt">Currently editing: SHIRT (Torso + Arms)</div>
                    <!-- Stacked canvases - only one visible at a time -->
                    <div class="canvas-stack" id="canvas-stack" style="width: 585px; height: 600px;">
                        <canvas id="shirt-canvas" width="585" height="600"></canvas>
                        <canvas id="pants-canvas" width="585" height="600"></canvas>
                    </div>
                    <div class="legend" id="legend">
                        <div class="legend-item"><div class="legend-color" style="background:#4CAF50;"></div> Torso</div>
                        <div class="legend-item"><div class="legend-color" style="background:#2196F3;"></div> Right Arm</div>
                        <div class="legend-item"><div class="legend-color" style="background:#FF9800;"></div> Left Arm</div>
                    </div>
                    <p class="info">Ghost template shows layout. Both shirt & pants always visible on 3D!</p>
                </div>
                <div class="panel">
                    <h3>3D Full Body Preview</h3>
                    <div id="three-container"></div>
                    <p class="info">Drag to rotate, scroll to zoom. Full outfit always displayed.</p>
                </div>
            </div>
        </div>

        <script>
            // --- CONSTANTS ---
            const CANVAS_W = 585;
            const CANVAS_H = 600;  // Increased to show arm/leg zones fully
            const TEMPLATE_URL = "https://raw.githubusercontent.com/Antosser/Roblox-Shirt-Template/master/template.png";

            // --- DUAL CANVAS STATE ---
            let currentMode = 'shirt';
            let shirtCanvas = null;  // Fabric.js canvas for shirt
            let pantsCanvas = null;  // Fabric.js canvas for pants

            // --- DROP ZONE GUIDES (Labels positioned above boxes) ---
            const DROP_ZONES = {
                torso_front: { x: 128, y: 128, w: 128, h: 128, color: '#4CAF50', label: 'FRONT', labelY: -20 },
                torso_back:  { x: 327, y: 128, w: 128, h: 128, color: '#4CAF50', label: 'BACK', labelY: -20 },
                right_arm:   { x: 0,   y: 323, w: 192, h: 236, color: '#2196F3', label: 'R. ARM/LEG', labelY: -20 },
                left_arm:    { x: 393, y: 323, w: 192, h: 236, color: '#FF9800', label: 'L. ARM/LEG', labelY: -20 }
            };

            // --- BODY PART DEFINITIONS ---
            const BODY_PARTS = {
                torso: {
                    size: [2, 2, 1],
                    position: [0, 0, 0],
                    textureSource: 'shirt',
                    faces: {
                        front:  { x: 128, y: 128, w: 128, h: 128 },
                        back:   { x: 327, y: 128, w: 128, h: 128 },
                        right:  { x: 64,  y: 128, w: 64,  h: 128 },
                        left:   { x: 256, y: 128, w: 64,  h: 128 },
                        top:    { x: 128, y: 0,   w: 128, h: 64 },
                        bottom: { x: 128, y: 256, w: 128, h: 64 }
                    }
                },
                rightArm: {
                    size: [1, 2, 1],
                    position: [-1.5, 0, 0],
                    textureSource: 'shirt',
                    faces: {
                        front:  { x: 64,  y: 388, w: 64, h: 128 },
                        back:   { x: 129, y: 388, w: 64, h: 128 },
                        right:  { x: 0,   y: 388, w: 64, h: 128 },
                        left:   { x: 128, y: 388, w: 64, h: 128 },
                        top:    { x: 64,  y: 323, w: 64, h: 64 },
                        bottom: { x: 64,  y: 516, w: 64, h: 43 }
                    }
                },
                leftArm: {
                    size: [1, 2, 1],
                    position: [1.5, 0, 0],
                    textureSource: 'shirt',
                    faces: {
                        front:  { x: 455, y: 388, w: 64, h: 128 },
                        back:   { x: 520, y: 388, w: 64, h: 128 },
                        right:  { x: 391, y: 388, w: 64, h: 128 },
                        left:   { x: 519, y: 388, w: 64, h: 128 },
                        top:    { x: 455, y: 323, w: 64, h: 64 },
                        bottom: { x: 455, y: 516, w: 64, h: 43 }
                    }
                },
                rightLeg: {
                    size: [1, 2, 1],
                    position: [-0.5, -2, 0],
                    textureSource: 'pants',
                    faces: {
                        front:  { x: 64,  y: 388, w: 64, h: 128 },
                        back:   { x: 129, y: 388, w: 64, h: 128 },
                        right:  { x: 0,   y: 388, w: 64, h: 128 },
                        left:   { x: 128, y: 388, w: 64, h: 128 },
                        top:    { x: 64,  y: 323, w: 64, h: 64 },
                        bottom: { x: 64,  y: 516, w: 64, h: 43 }
                    }
                },
                leftLeg: {
                    size: [1, 2, 1],
                    position: [0.5, -2, 0],
                    textureSource: 'pants',
                    faces: {
                        front:  { x: 455, y: 388, w: 64, h: 128 },
                        back:   { x: 520, y: 388, w: 64, h: 128 },
                        right:  { x: 391, y: 388, w: 64, h: 128 },
                        left:   { x: 519, y: 388, w: 64, h: 128 },
                        top:    { x: 455, y: 323, w: 64, h: 64 },
                        bottom: { x: 455, y: 516, w: 64, h: 43 }
                    }
                },
                head: {
                    size: [1.2, 1.2, 1.2],
                    position: [0, 1.6, 0],
                    textureSource: 'none',
                    faces: {
                        front: null, back: null, right: null,
                        left: null, top: null, bottom: null
                    }
                }
            };
            
            const FACE_ORDER = ['right', 'left', 'top', 'bottom', 'front', 'back'];
            
            // Fit-to-zone coordinates
            const FIT_ZONES = {
                front: { x: 128, y: 128, w: 128, h: 128 },
                back:  { x: 327, y: 128, w: 128, h: 128 },
                r_arm: { x: 64,  y: 388, w: 64,  h: 128 },
                l_arm: { x: 455, y: 388, w: 64,  h: 128 }
            };

            // --- INITIALIZE BOTH FABRIC.JS CANVASES ---
            function initCanvas(canvasId) {
                const canvas = new fabric.Canvas(canvasId, { 
                    backgroundColor: '#ffffff',
                    preserveObjectStacking: true
                });
                
                // Load ghost template as BACKGROUND (30% opacity)
                fabric.Image.fromURL(TEMPLATE_URL, function(img) {
                    img.set({
                        left: 0, top: 0,
                        selectable: false,
                        evented: false,
                        opacity: 0.3  // Ghost overlay at 30%
                    });
                    img.scaleToWidth(CANVAS_W);
                    canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas));
                }, { crossOrigin: 'anonymous' });
                
                // Draw drop zone guides with labels ABOVE boxes
                Object.keys(DROP_ZONES).forEach(key => {
                    const zone = DROP_ZONES[key];
                    
                    // Label positioned ABOVE the box
                    const text = new fabric.Text(zone.label, {
                        left: zone.x + zone.w / 2,
                        top: zone.y + (zone.labelY || -20),
                        fontSize: 14,
                        fontWeight: 'bold',
                        fill: zone.color,
                        originX: 'center',
                        selectable: false,
                        evented: false,
                        isGuide: true
                    });
                    
                    // Dashed rectangle box
                    const rect = new fabric.Rect({
                        left: zone.x,
                        top: zone.y,
                        width: zone.w,
                        height: zone.h,
                        fill: 'transparent',
                        stroke: zone.color,
                        strokeWidth: 2,
                        strokeDashArray: [5, 5],
                        selectable: false,
                        evented: false,
                        isGuide: true
                    });
                    
                    canvas.add(text);
                    canvas.add(rect);
                });
                
                // Update 3D on any change
                canvas.on('object:modified', updateAllTextures);
                canvas.on('object:added', updateAllTextures);
                canvas.on('object:removed', updateAllTextures);
                canvas.on('object:scaling', updateAllTextures);
                canvas.on('object:moving', updateAllTextures);
                canvas.on('object:rotating', updateAllTextures);
                
                return canvas;
            }
            
            // Initialize both canvases
            shirtCanvas = initCanvas('shirt-canvas');
            pantsCanvas = initCanvas('pants-canvas');
            
            // Hide pants canvas initially
            document.querySelector('#pants-canvas').parentElement.classList.add('hidden-canvas');
            
            // --- GET ACTIVE CANVAS ---
            function getActiveCanvas() {
                return currentMode === 'shirt' ? shirtCanvas : pantsCanvas;
            }

            // --- MODE SWITCHING (just toggle visibility) ---
            function switchMode(newMode) {
                if (newMode === currentMode) return;
                
                currentMode = newMode;
                
                // Toggle canvas visibility
                const shirtContainer = document.querySelector('#shirt-canvas').parentElement;
                const pantsContainer = document.querySelector('#pants-canvas').parentElement;
                
                if (newMode === 'shirt') {
                    shirtContainer.classList.remove('hidden-canvas');
                    pantsContainer.classList.add('hidden-canvas');
                } else {
                    shirtContainer.classList.add('hidden-canvas');
                    pantsContainer.classList.remove('hidden-canvas');
                }
                
                // Update UI label
                const modeLabel = document.getElementById('mode-label');
                if (newMode === 'shirt') {
                    modeLabel.textContent = 'Currently editing: SHIRT (Torso + Arms)';
                    modeLabel.className = 'mode-indicator shirt';
                } else {
                    modeLabel.textContent = 'Currently editing: PANTS (Legs)';
                    modeLabel.className = 'mode-indicator pants';
                }
                
                // Toggle torso-only buttons
                document.querySelectorAll('.torso-only').forEach(btn => {
                    if (newMode === 'shirt') {
                        btn.classList.remove('hidden');
                    } else {
                        btn.classList.add('hidden');
                    }
                });
                
                // Update legend based on mode
                const legend = document.getElementById('legend');
                if (newMode === 'shirt') {
                    legend.innerHTML = `
                        <div class="legend-item"><div class="legend-color" style="background:#4CAF50;"></div> Torso</div>
                        <div class="legend-item"><div class="legend-color" style="background:#2196F3;"></div> Right Arm</div>
                        <div class="legend-item"><div class="legend-color" style="background:#FF9800;"></div> Left Arm</div>
                    `;
                } else {
                    legend.innerHTML = `
                        <div class="legend-item"><div class="legend-color" style="background:#2196F3;"></div> Right Leg</div>
                        <div class="legend-item"><div class="legend-color" style="background:#FF9800;"></div> Left Leg</div>
                    `;
                }
                
                // 3D is always up-to-date since it reads from both canvases
            }

            // Mode toggle event listeners
            document.querySelectorAll('input[name="editMode"]').forEach(radio => {
                radio.addEventListener('change', function() {
                    switchMode(this.value);
                });
            });

            // File upload - add to active canvas
            document.getElementById('img-upload').addEventListener('change', function(e) {
                const file = e.target.files[0];
                if (!file) return;
                
                const reader = new FileReader();
                reader.onload = function(event) {
                    fabric.Image.fromURL(event.target.result, function(img) {
                        const canvas = getActiveCanvas();
                        img.set({ left: 128, top: 128 });
                        img.scaleToWidth(128);
                        canvas.add(img);
                        canvas.setActiveObject(img);
                        canvas.bringToFront(img);
                        canvas.renderAll();
                        updateAllTextures();
                    });
                };
                reader.readAsDataURL(file);
            });

            // Fit to zone - on active canvas
            window.fitToZone = function(zoneName) {
                const canvas = getActiveCanvas();
                const activeObj = canvas.getActiveObject();
                if (!activeObj) { alert("Select an image first!"); return; }
                
                const zone = FIT_ZONES[zoneName];
                if (!zone) return;
                
                activeObj.set({
                    left: zone.x,
                    top: zone.y,
                    scaleX: zone.w / activeObj.width,
                    scaleY: zone.h / activeObj.height
                });
                activeObj.setCoords();
                canvas.bringToFront(activeObj);
                canvas.renderAll();
                updateAllTextures();
            };
            
            // --- HELPER: Get clean canvas element for texture ---
            function getCleanCanvasElement(fabricCanvas) {
                // Hide guides for clean export
                const guides = fabricCanvas.getObjects().filter(obj => obj.isGuide);
                guides.forEach(obj => obj.set('visible', false));
                
                const activeObj = fabricCanvas.getActiveObject();
                fabricCanvas.discardActiveObject();
                fabricCanvas.renderAll();
                
                const canvasElement = fabricCanvas.toCanvasElement();
                
                // Restore
                guides.forEach(obj => obj.set('visible', true));
                if (activeObj) fabricCanvas.setActiveObject(activeObj);
                fabricCanvas.renderAll();
                
                return canvasElement;
            }
            
            // Delete selected object
            window.deleteSelected = function() {
                const canvas = getActiveCanvas();
                const activeObj = canvas.getActiveObject();
                if (!activeObj) {
                    alert('Select an image to delete!');
                    return;
                }
                if (activeObj.isGuide) {
                    alert('Cannot delete guide elements!');
                    return;
                }
                canvas.remove(activeObj);
                canvas.discardActiveObject();
                canvas.renderAll();
                updateAllTextures();
            };
            
            // Download texture from specific canvas - Robust Base64 method
            window.downloadTexture = function(type) {
                const canvas = (type === 'shirt') ? shirtCanvas : pantsCanvas;
                const cleanCanvas = getCleanCanvasElement(canvas);
                
                // Prompt user for filename
                const defaultName = (type === 'shirt') ? 'roblox_shirt_design' : 'roblox_pants_design';
                let filename = prompt("Enter filename:", defaultName);
                
                // If user cancels, stop download
                if (filename === null) return;
                
                // Fix: Trim and default if empty string provided
                filename = filename.trim() || defaultName;
                
                // Enforce .png extension
                if (!filename.toLowerCase().endsWith('.png')) {
                    filename += '.png';
                }
                
                const dataURL = cleanCanvas.toDataURL('image/png');
                const link = document.createElement('a');
                link.download = filename; 
                link.href = dataURL;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            };

            // --- THREE.JS SETUP ---
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x1a1a1a);
            
            const camera = new THREE.PerspectiveCamera(40, 400/520, 0.1, 100);
            camera.position.set(0, 0, 8);
            
            const renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(400, 520);
            document.getElementById('three-container').appendChild(renderer.domElement);

            // OrbitControls
            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.1;
            controls.enablePan = false;
            controls.minDistance = 3;
            controls.maxDistance = 12;

            // Lighting
            scene.add(new THREE.AmbientLight(0xffffff, 0.7));
            const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
            dirLight.position.set(3, 4, 5);
            scene.add(dirLight);
            const backLight = new THREE.DirectionalLight(0xffffff, 0.3);
            backLight.position.set(-2, 2, -3);
            scene.add(backLight);

            // --- CREATE BODY PARTS WITH MULTI-MATERIAL ---
            const bodyMeshes = {};
            const faceCanvases = {};
            const faceTextures = {};
            
            const skinMaterial = new THREE.MeshStandardMaterial({ 
                color: 0xd4a574,
                roughness: 0.8
            });
            
            // Create each body part
            Object.keys(BODY_PARTS).forEach(partName => {
                const part = BODY_PARTS[partName];
                const [w, h, d] = part.size;
                const [px, py, pz] = part.position;
                
                faceCanvases[partName] = {};
                faceTextures[partName] = {};
                
                const materials = FACE_ORDER.map(faceName => {
                    const region = part.faces[faceName];
                    
                    if (!region) {
                        return skinMaterial;
                    }
                    
                    const canvas = document.createElement('canvas');
                    canvas.width = 128;
                    canvas.height = 128;
                    const ctx = canvas.getContext('2d');
                    
                    // Default color based on texture source
                    if (part.textureSource === 'pants') {
                        ctx.fillStyle = '#3d5a80';
                    } else {
                        ctx.fillStyle = '#ffffff';
                    }
                    ctx.fillRect(0, 0, 128, 128);
                    
                    faceCanvases[partName][faceName] = canvas;
                    
                    const texture = new THREE.CanvasTexture(canvas);
                    texture.minFilter = THREE.LinearFilter;
                    texture.magFilter = THREE.LinearFilter;
                    faceTextures[partName][faceName] = texture;
                    
                    return new THREE.MeshStandardMaterial({
                        map: texture,
                        roughness: 0.7
                    });
                });
                
                const geometry = new THREE.BoxGeometry(w, h, d);
                const mesh = new THREE.Mesh(geometry, materials);
                mesh.position.set(px, py, pz);
                scene.add(mesh);
                bodyMeshes[partName] = mesh;
            });

            // Animation loop
            function animate() {
                requestAnimationFrame(animate);
                controls.update();
                renderer.render(scene, camera);
            }
            animate();

            // --- 3D UPDATE: Always reads from BOTH canvases ---
            function updateAllTextures() {
                // Get clean canvas elements from BOTH canvases
                const shirtCanvasEl = getCleanCanvasElement(shirtCanvas);
                const pantsCanvasEl = getCleanCanvasElement(pantsCanvas);
                
                // Update each body part's face textures
                Object.keys(BODY_PARTS).forEach(partName => {
                    const part = BODY_PARTS[partName];
                    
                    // Determine which source canvas to use based on body part
                    let sourceCanvas;
                    if (part.textureSource === 'shirt') {
                        sourceCanvas = shirtCanvasEl;
                    } else if (part.textureSource === 'pants') {
                        sourceCanvas = pantsCanvasEl;
                    } else {
                        return; // Skip head
                    }
                    
                    FACE_ORDER.forEach(faceName => {
                        const region = part.faces[faceName];
                        if (!region) return;
                        
                        const canvas = faceCanvases[partName][faceName];
                        if (!canvas) return;
                        
                        const ctx = canvas.getContext('2d');
                        
                        ctx.fillStyle = '#ffffff';
                        ctx.fillRect(0, 0, 128, 128);
                        ctx.drawImage(
                            sourceCanvas,
                            region.x, region.y, region.w, region.h,
                            0, 0, 128, 128
                        );
                        
                        faceTextures[partName][faceName].needsUpdate = true;
                    });
                });
            }
            
            // Initial update after canvases are ready
            setTimeout(updateAllTextures, 1000);
        </script>
    </body>
    </html>
    """

def main():
    st.set_page_config(page_title="Roblox Clothing Generator", page_icon="👔", layout="wide")
    
    st.title("👔 Roblox Clothing Generator")
    
    # Setup - download template if needed
    download_template()
    
    # --- Sidebar Controls ---
    with st.sidebar:
        st.header("⚙️ Configuration")
        mode_selection = st.radio("App Mode:", ["Ai Generator", "Manual Editor"])
        
        if mode_selection == "Ai Generator":
            clothing_type = st.radio("Clothing Type:", ["Classic Shirt", "Classic Pants"])
            mode = st.selectbox(
                "Generation Mode:",
                ["Logo Mode", "Pattern Mode"],
                help="Logo Mode: Centers a single image. Pattern Mode: Tiles the image."
            )
    
    if mode_selection == "Ai Generator":
        st.write("Generate custom Roblox shirt and pants textures using AI!")
        
        # UI Controls
        placeholder_text = "e.g., golden dragon logo" if clothing_type == "Classic Shirt" else "e.g., blue denim jeans fabric"
        prompt = st.text_input(
            f"Describe your {clothing_type.lower().replace('classic ', '')} design:",
            placeholder=placeholder_text
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            generate_btn = st.button("🚀 Generate", type="primary")
        
        # Generation Logic
        if generate_btn:
            if not prompt:
                st.warning("Please enter a design description.")
                return
            
            client = get_openai_client()
            # Append "texture" to prompt to guide DALL-E towards flat textures
            full_prompt = f"{prompt}, flat texture, top down view, no perspective"
            ai_image = generate_image(client, full_prompt)
            
            if ai_image:
                with st.spinner("Processing image..."):
                    # Route based on mode
                    if mode == "Logo Mode":
                        base_image = create_logo_mode_image(ai_image)
                    else:
                        base_image = create_pattern_mode_image(ai_image)
                    
                    # Apply template overlay
                    final_image = apply_template_overlay(base_image)
                
                # Store final image in session state
                st.session_state['final_image'] = final_image
                st.success(f"✅ {clothing_type} generated!")

        # Display and Download
        if 'final_image' in st.session_state:
            final_image = st.session_state['final_image']
            
            st.image(final_image, caption=f"Generated {clothing_type}", use_container_width=False)
            
            # Custom Filename Input
            default_name = "roblox_shirt" if clothing_type == "Classic Shirt" else "roblox_pants"
            custom_name = st.text_input("Filename:", value=default_name)
            if not custom_name.endswith(".png"):
                custom_name += ".png"
                
            # Download button
            buf = io.BytesIO()
            final_image.save(buf, format="PNG")
            st.download_button(
                label="📥 Download PNG",
                data=buf.getvalue(),
                file_name=custom_name,
                mime="image/png"
            )

    else:
        # --- MANUAL EDITOR MODE ---
        st.header("🎨 Manual Editor & 3D Preview")
        st.write("Upload an image, drag/resize it on the template, and see the real-time preview!")
        st.info("💡 Note: The 2D editor allows you to place images exactly where they belong on the template.")
        
        # Render the HTML/JS component
        # Render the HTML/JS component
        components.html(get_editor_html(), height=850, scrolling=True)

if __name__ == "__main__":
    main()
