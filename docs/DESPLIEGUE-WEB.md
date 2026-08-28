# Publicar la web de easypdf.surf

La web vive en `site/` y son archivos estaticos: no hay servidor ni base de
datos. La pagina principal esta en **ingles** (`/`) y la version en espanol
cuelga de `/es/`; las dos se generan del mismo guion para que no se descuadren:

```bash
python tools/build_site.py     # escribe site/index.html, site/es/index.html,
                               # robots.txt y sitemap.xml
```

## Los numeros de la portada

- **Descargas**: las cuenta GitHub en los archivos de cada *release*. La pagina
  suma los `download_count` de todos los archivos con una peticion a la API
  publica de GitHub y guarda el resultado una hora en el navegador. Para que
  haya numeros hace falta haber publicado una release: se hace con el flujo
  *Publicar release* de la pestana Actions. Ojo: los archivos servidos como
  `raw` del repositorio (los enlaces de `build/`) **no** llevan cuenta; solo
  los de las releases.
- **Visitas de hoy y totales**: contador publico y sin cookies de
  [counterapi.dev](https://counterapi.dev). Se suma una vez por navegador y
  dia, no guarda nada de quien visita, y si el servicio falla el numero
  simplemente no aparece (nunca se ensena una cifra inventada).

Si algun dia quieres analitica de verdad (paginas mas vistas, referencias, de
que pais llegan), cambia `VISITS_API` en `tools/build_site.py` por
[GoatCounter](https://www.goatcounter.com) o [Plausible](https://plausible.io):
ambos son sin cookies y tienen plan gratuito para proyectos abiertos.

## Render (opcion oficial)

1. En Render: **New → Blueprint** y elegir este repositorio. Render lee
   `render.yaml` y crea el sitio estatico apuntando a `site/`.
   (Tambien se puede a mano con **New → Static Site**: *Build command* vacio y
   *Publish directory* `site`.)
2. Cada `git push` a `main` vuelve a desplegar.
3. **Dominio propio**: Settings → *Custom Domains* → anadir `easypdf.surf` y
   `www.easypdf.surf`. Render muestra ahi los registros DNS exactos que hay que
   crear en el proveedor del dominio: normalmente un registro **A** para el
   dominio raiz apuntando a la IP que indique Render, y un **CNAME** de `www`
   hacia `<nombre-del-sitio>.onrender.com`.
4. El certificado HTTPS lo emite Render automaticamente cuando el DNS ya apunta
   a ellos (puede tardar unos minutos).

> Los instaladores no se copian a la web: los enlaces de descarga apuntan a los
> archivos de `build/` en GitHub, asi el sitio pesa unos pocos cientos de kB.

## GitHub Pages (espejo)

El flujo `.github/workflows/pages.yml` copia `site/` a la rama `gh-pages` en
cada cambio. Si se activa Pages sobre esa rama queda un espejo de la web en
`https://mefardales.github.io/easypdf/`. No lleva archivo `CNAME` a proposito:
el dominio lo gestiona Render.

## SEO

Lo que ya trae la pagina:

- Un titulo y una descripcion distintos por idioma, con las palabras que la
  gente busca de verdad ("free pdf reader", "lector de PDF gratis", "anotar PDF").
- `canonical` y `hreflang` (en, es y `x-default` apuntando al ingles) en las dos
  paginas.
- Datos estructurados JSON-LD: `SoftwareApplication` (con precio 0) y
  `FAQPage` con las preguntas frecuentes.
- Etiquetas Open Graph y Twitter Card con la captura, para que se vea bien al
  compartir el enlace.
- `robots.txt` y `sitemap.xml` con las dos URLs.
- HTML con estructura semantica, un unico `h1`, textos alternativos en las
  imagenes y enlace para saltar al contenido.

Despues del primer despliegue conviene dar de alta el dominio en
[Google Search Console](https://search.google.com/search-console) y enviar
`https://easypdf.surf/sitemap.xml`.
