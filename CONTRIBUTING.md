# Contribuir a easypdf.surf

Gracias por querer echar una mano. easypdf.surf quiere seguir siendo **sencillo**: antes de
anadir una funcion, piensa si una persona que solo quiere leer y anotar un PDF la
echaria de menos.

## Preparar el entorno

```bash
git clone https://github.com/mefardales/easypdf.git
cd easypdf
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m easypdf                # arranca la aplicacion
```

## Antes de abrir un pull request

```bash
pytest -q                        # todas las pruebas en verde
ruff check src tests tools       # sin avisos de estilo
```

Si tocas la interfaz, anade una prueba en `tests/test_ui.py`: se ejecutan con la
plataforma Qt `offscreen`, asi que funcionan sin pantalla y en integracion continua.

## Como esta organizado el codigo

- `model.py` es Python puro: sin Qt y sin PyMuPDF. Toda la logica que se pueda probar
  sin interfaz deberia vivir ahi.
- `document.py` y `annotations.py` son la unica frontera con PyMuPDF.
- La interfaz (`ui/`) no habla nunca con PyMuPDF directamente.
- Las coordenadas de las anotaciones estan siempre en **puntos PDF** con el origen
  arriba a la izquierda. No guardes coordenadas de pantalla.

## Estilo

- Textos de la interfaz en espanol; nombres de funciones y variables en ingles.
- Comentarios solo donde el codigo no se explica solo.
- Lineas de hasta 100 caracteres (lo comprueba `ruff`).

## Reportar un fallo

Abre una incidencia indicando la version de EasyPDF, tu sistema operativo y, si
puedes, un PDF de ejemplo (o uno equivalente sin datos personales) y los pasos para
reproducirlo.

## Licencia de las aportaciones

Al enviar un pull request aceptas publicar tu codigo bajo la
[GNU AGPL v3 o posterior](LICENSE), la misma licencia del proyecto.
