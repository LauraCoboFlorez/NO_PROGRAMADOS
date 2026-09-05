# Explorador automático de datos

Aplicación web construida con Streamlit para cargar archivos tabulares y ejecutar automáticamente un análisis exploratorio de datos. No incluye datasets predeterminados, no usa rutas fijas y no almacena permanentemente los archivos cargados.

## Funcionalidades

- Carga de archivos CSV, XLSX y XLS.
- Reconocimiento asistido de columnas de fecha por nombre.
- Filtros por fecha, categoría y rango numérico.
- Indicadores de filas, columnas, duplicados y valores faltantes.
- Resumen de tipos Pandas y tipos analíticos.
- Identificación y visualización de registros duplicados.
- Resumen y gráfico interactivo de valores faltantes.
- Estadísticas descriptivas numéricas y categóricas.
- Histogramas, diagramas de caja y gráficos de frecuencias.
- Correlaciones Pearson, Spearman y Kendall.
- Detección de valores atípicos mediante el método IQR.
- Tabla interactiva con selección de columnas.
- Descarga en CSV de datos filtrados y detecciones de atípicos.

## Formatos admitidos

- `.csv`
- `.xlsx`, leído con `openpyxl`
- `.xls`, leído con `xlrd`

## Estructura del repositorio

```text
explorador-automatico-datos/
├── app.py
├── requirements.txt
└── README.md
```

No se debe agregar ningún dataset al repositorio.

## Instalación local

Requisitos previos:

- Python 3.11 recomendado.
- Git opcional para control de versiones.

```bash
python -m venv .venv
```

Activación en Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Activación en macOS o Linux:

```bash
source .venv/bin/activate
```

Instala las dependencias:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Ejecución local

```bash
streamlit run app.py
```

Streamlit mostrará una dirección local, normalmente `http://localhost:8501`.

## Publicación en GitHub

1. Crea un repositorio vacío en GitHub.
2. Copia `app.py`, `requirements.txt` y `README.md` en la raíz.
3. Desde la carpeta del proyecto ejecuta:

```bash
git init
git add app.py requirements.txt README.md
git commit -m "Crear Explorador automático de datos"
git branch -M main
git remote add origin https://github.com/USUARIO/REPOSITORIO.git
git push -u origin main
```

Reemplaza `USUARIO` y `REPOSITORIO` por los valores reales.

## Despliegue en Streamlit Community Cloud

1. Publica el repositorio en GitHub.
2. Accede a Streamlit Community Cloud e inicia sesión con GitHub.
3. Selecciona **Create app**.
4. Elige el repositorio, la rama `main` y el archivo principal `app.py`.
5. Pulsa **Deploy**.

No se requieren secretos, variables de entorno ni configuración adicional.

> Esta aplicación usa un servidor Python de Streamlit. Por esa razón no puede ejecutarse como un sitio estático puro en GitHub Pages. Netlify y Vercel tampoco ejecutan directamente una sesión persistente de Streamlit sin una arquitectura adicional. Streamlit Community Cloud es la opción de despliegue prevista.

## Privacidad y uso responsable

Los datos se procesan durante la sesión activa de la aplicación. Evita cargar datos personales, confidenciales, sensibles o sujetos a restricciones legales. El análisis exploratorio no sustituye la evaluación de una persona experta. Una correlación no implica causalidad y una observación atípica no necesariamente es un error.

## Limitaciones conocidas

- Los archivos muy grandes dependen de la memoria y los límites de recursos del entorno de despliegue.
- La detección automática de fechas utiliza el nombre de la columna y un umbral de conversión; siempre debe validarse visualmente.
- Los CSV con estructuras poco comunes pueden requerir normalización previa.
- La clasificación entre variable categórica y texto usa una heurística basada en cardinalidad.
- El método IQR puede no ser apropiado para todas las distribuciones o áreas de conocimiento.
- Las correlaciones solo describen asociación estadística entre variables numéricas.
- Los filtros categóricos no incluyen los valores faltantes como categoría seleccionable.

## Pruebas funcionales recomendadas

1. Abrir la aplicación sin cargar un archivo y verificar la bienvenida y la detención del análisis.
2. Cargar un CSV UTF-8, un CSV Latin-1, un XLSX y un XLS válidos.
3. Intentar cargar un archivo vacío o dañado y comprobar el mensaje de error.
4. Probar datasets con una sola columna.
5. Probar datasets sin variables numéricas y sin variables categóricas.
6. Probar columnas completamente vacías.
7. Validar filtros de fecha, categoría y número, incluidos valores faltantes.
8. Aplicar filtros que produzcan cero filas.
9. Confirmar que los cuatro indicadores cambian al filtrar.
10. Verificar duplicados completos con `keep=False`.
11. Comprobar estadísticas para las tres opciones.
12. Probar histogramas, cajas agrupadas y categorías con más de 30 valores.
13. Calcular los tres métodos de correlación.
14. Cambiar el factor IQR y comprobar límites, conteos y filas originales.
15. Descargar ambos CSV y abrirlos en Excel verificando tildes y caracteres especiales.
16. Desplegar desde un repositorio limpio en Streamlit Community Cloud.

## Solución de problemas

- **`ModuleNotFoundError`**: activa el entorno virtual y ejecuta `pip install -r requirements.txt`.
- **Error al abrir XLSX**: verifica que `openpyxl` esté instalado y que el archivo no esté dañado.
- **Error al abrir XLS**: verifica que `xlrd` esté instalado y que el archivo sea realmente un libro de Excel antiguo.
- **CSV leído en una sola columna**: revisa si utiliza un separador o estructura no estándar.
- **Fechas no reconocidas**: cambia el encabezado para incluir “fecha” o “date”, o normaliza la columna antes de cargarla.
- **Aplicación lenta o sin memoria**: reduce el tamaño del archivo o elimina columnas innecesarias antes de cargarlo.
- **No aparecen correlaciones**: se necesitan al menos dos columnas numéricas con datos válidos.
- **No aparecen atípicos**: selecciona variables numéricas y revisa el factor IQR.
- **Falla el despliegue**: confirma que los tres archivos estén en la raíz y que el archivo principal configurado sea `app.py`.
