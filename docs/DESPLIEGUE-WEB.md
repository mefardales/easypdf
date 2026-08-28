# Publicar la web de easypdf.surf

La web vive en `site/` y son archivos estaticos: no hay servidor ni base de
datos. Las dos paginas (espanol e ingles) se generan con un guion para que no
se descuadren entre ellas:

```bash
python tools/build_site.py     # escribe site/index.html, site/en/index.html,
                               # robots.txt y sitemap.xml
```

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
  gente busca de verdad ("lector de PDF gratis", "anotar PDF").
- `canonical` y `hreflang` (es, en y `x-default`) en las dos paginas.
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
