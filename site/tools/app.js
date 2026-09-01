/* easypdf.surf tools - everything runs in the browser.
 *
 * No file ever leaves the device: there is no upload, no fetch to any server
 * and no analytics here. pdf-lib writes the PDFs, pdf.js draws the previews,
 * and both are served from this same site (see vendor/).
 *
 * Every page sets document.body.dataset.tool and window.T with its texts.
 */
(function () {
  "use strict";

  var T = window.T || {};
  var TOOL = document.body.dataset.tool;
  // Shared assets live once under /tools/; the Spanish pages under /es/tools/
  // point at the very same files instead of carrying a second copy.
  var BASE = document.body.dataset.base || "/tools/";

  // ---------------------------------------------------------------- helpers
  function $(sel, root) { return (root || document).querySelector(sel); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function say(text, kind) {
    var s = $("#status");
    if (!s) return;
    s.textContent = text || "";
    s.className = "st" + (kind ? " " + kind : "");
  }
  function size(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " kB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }
  function stem(name) { return String(name || "document").replace(/\.[^.]+$/, ""); }
  function busy(on) {
    var b = $("#go");
    if (!b) return;
    b.classList.toggle("busy", !!on);
    b.disabled = !!on;
  }

  // Chrome refuses more than one programmatic download in a row unless they
  // are spaced out, so results are offered as links the user taps instead.
  function offer(blob, name) {
    var url = URL.createObjectURL(blob);
    var a = el("a", "dl");
    a.href = url;
    a.download = name;
    a.append(document.createTextNode("↓ " + name), el("span", "sz", " "));
    a.querySelector(".sz").textContent = " (" + size(blob.size) + ")";
    return a;
  }
  function results(title, note, nodes) {
    var box = $("#done");
    box.innerHTML = "";
    box.append(el("h2", null, title));
    if (note) box.append(el("p", null, note));
    var outs = el("div", "outs");
    nodes.forEach(function (n) { outs.append(n); });
    box.append(outs);
    box.hidden = false;
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // ------------------------------------------------------------------ files
  function read(file) {
    return new Promise(function (ok, no) {
      var r = new FileReader();
      r.onload = function () { ok(new Uint8Array(r.result)); };
      r.onerror = function () { no(new Error(T.err_read)); };
      r.readAsArrayBuffer(file);
    });
  }

  var dropZone = $("#drop"), input = $("#file");

  function wireDrop(onFiles) {
    if (!dropZone) return;
    dropZone.addEventListener("click", function () { input.click(); });
    dropZone.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
    });
    input.addEventListener("change", function () {
      if (input.files.length) onFiles(Array.prototype.slice.call(input.files));
      input.value = "";                    // so the same file can be picked twice
    });
    ["dragenter", "dragover"].forEach(function (ev) {
      dropZone.addEventListener(ev, function (e) {
        e.preventDefault();
        dropZone.classList.add("over");
      });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      dropZone.addEventListener(ev, function (e) {
        e.preventDefault();
        dropZone.classList.remove("over");
      });
    });
    dropZone.addEventListener("drop", function (e) {
      var list = e.dataTransfer && e.dataTransfer.files;
      if (list && list.length) onFiles(Array.prototype.slice.call(list));
    });
  }

  // ----------------------------------------------------------------- pdf.js
  var pdfjsReady = null;
  function pdfjs() {
    if (!pdfjsReady) {
      pdfjsReady = load(BASE + "vendor/pdf.min.js").then(function () {
        window.pdfjsLib.GlobalWorkerOptions.workerSrc = BASE + "vendor/pdf.worker.min.js";
        return window.pdfjsLib;
      });
    }
    return pdfjsReady;
  }
  var pdflibReady = null;
  function pdflib() {
    if (!pdflibReady) {
      pdflibReady = load(BASE + "vendor/pdf-lib.min.js").then(function () { return window.PDFLib; });
    }
    return pdflibReady;
  }
  // Loaded on demand: the landing of each tool stays light until a file is in.
  function load(src) {
    return new Promise(function (ok, no) {
      var s = document.createElement("script");
      s.src = src;
      s.onload = ok;
      s.onerror = function () { no(new Error(T.err_lib)); };
      document.head.append(s);
    });
  }

  // pdf.js detaches the buffer it is handed, so it always gets a copy.
  function openDoc(bytes) {
    return pdfjs().then(function (lib) {
      return lib.getDocument({ data: bytes.slice(0), isEvalSupported: false }).promise;
    });
  }

  function drawPage(page, canvas, box) {
    var v0 = page.getViewport({ scale: 1 });
    var scale = Math.min(box / v0.width, (box * 1.414) / v0.height);
    var vp = page.getViewport({ scale: scale });
    var ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(vp.width * ratio);
    canvas.height = Math.floor(vp.height * ratio);
    canvas.style.width = Math.floor(vp.width) + "px";
    canvas.style.height = Math.floor(vp.height) + "px";
    var ctx = canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    return page.render({ canvasContext: ctx, viewport: vp }).promise;
  }

  // ------------------------------------------------------------------- zip
  // Stored (uncompressed) entries only: what goes in is JPEG or PDF, both
  // already compressed, so deflating them would buy nothing and cost a lot.
  var CRC = (function () {
    var t = new Uint32Array(256);
    for (var i = 0; i < 256; i++) {
      var c = i;
      for (var k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[i] = c >>> 0;
    }
    return t;
  })();
  function crc32(data) {
    var c = 0xffffffff;
    for (var i = 0; i < data.length; i++) c = CRC[(c ^ data[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }
  function zip(entries) {
    var parts = [], central = [], offset = 0, enc = new TextEncoder();
    entries.forEach(function (e) {
      var name = enc.encode(e.name), crc = crc32(e.data), n = e.data.length;
      var local = new Uint8Array(30 + name.length), v = new DataView(local.buffer);
      v.setUint32(0, 0x04034b50, true); v.setUint16(4, 20, true);
      v.setUint16(6, 0, true); v.setUint16(8, 0, true);
      v.setUint16(10, 0, true); v.setUint16(12, 0x2821, true);   // fixed date
      v.setUint32(14, crc, true); v.setUint32(18, n, true); v.setUint32(22, n, true);
      v.setUint16(26, name.length, true); v.setUint16(28, 0, true);
      local.set(name, 30);
      parts.push(local, e.data);

      var cd = new Uint8Array(46 + name.length), w = new DataView(cd.buffer);
      w.setUint32(0, 0x02014b50, true); w.setUint16(4, 20, true); w.setUint16(6, 20, true);
      w.setUint16(8, 0, true); w.setUint16(10, 0, true);
      w.setUint16(12, 0, true); w.setUint16(14, 0x2821, true);
      w.setUint32(16, crc, true); w.setUint32(20, n, true); w.setUint32(24, n, true);
      w.setUint16(28, name.length, true);
      w.setUint32(42, offset, true);
      cd.set(name, 46);
      central.push(cd);
      offset += local.length + n;
    });
    var csize = central.reduce(function (a, c) { return a + c.length; }, 0);
    var end = new Uint8Array(22), z = new DataView(end.buffer);
    z.setUint32(0, 0x06054b50, true);
    z.setUint16(8, entries.length, true); z.setUint16(10, entries.length, true);
    z.setUint32(12, csize, true); z.setUint32(16, offset, true);
    return new Blob(parts.concat(central, [end]), { type: "application/zip" });
  }

  // ------------------------------------------------------------ page ranges
  // "1-3, 7, 12-" over a document of `total` pages, as zero-based indexes.
  function parseRange(text, total) {
    var out = [], seen = {};
    String(text).split(",").forEach(function (chunk) {
      chunk = chunk.trim();
      if (!chunk) return;
      var m = /^(\d*)\s*-\s*(\d*)$/.exec(chunk);
      var from, to;
      if (m) {
        from = m[1] ? parseInt(m[1], 10) : 1;
        to = m[2] ? parseInt(m[2], 10) : total;
      } else if (/^\d+$/.test(chunk)) {
        from = to = parseInt(chunk, 10);
      } else {
        throw new Error(T.err_range.replace("{0}", chunk));
      }
      if (from > to) { var s = from; from = to; to = s; }
      for (var i = from; i <= to; i++) {
        if (i >= 1 && i <= total && !seen[i]) { seen[i] = 1; out.push(i - 1); }
      }
    });
    return out;
  }

  function loadPdf(bytes) {
    return pdflib().then(function (lib) {
      return lib.PDFDocument.load(bytes, { updateMetadata: false }).catch(function (e) {
        throw new Error(/encrypt/i.test(e && e.message) ? T.err_locked : T.err_pdf);
      });
    });
  }

  // ===================================================================== app
  var state = { files: [], pages: [], doc: null, bytes: null, name: "" };

  function fail(e) {
    busy(false);
    say((e && e.message) || String(e), "bad");
  }

  function ready(on, note) {
    $("#go").disabled = !on;
    say(note || "");
  }

  // -- shared: one PDF in, page thumbnails out ------------------------------
  function takeOnePdf(files, afterThumbs) {
    var file = files[0];
    if (!file) return;
    if (!/\.pdf$/i.test(file.name)) { say(T.err_not_pdf, "bad"); return; }
    say(T.reading);
    state.name = stem(file.name);
    read(file)
      .then(function (bytes) {
        state.bytes = bytes;
        return openDoc(bytes);
      })
      .then(function (doc) {
        state.doc = doc;
        state.pages = [];
        for (var i = 0; i < doc.numPages; i++) {
          state.pages.push({ n: i, rot: 0, keep: true, on: false });
        }
        $("#drop").hidden = true;
        var ctl = $("#ctl");
        if (ctl) ctl.hidden = false;
        return paint(doc);
      })
      .then(function () { afterThumbs && afterThumbs(); })
      .catch(fail);
  }

  function paint(doc) {
    var grid = $("#grid");
    grid.innerHTML = "";
    grid.hidden = false;
    var jobs = state.pages.map(function (p, i) {
      var li = el("li", "card");
      li.dataset.i = i;
      var sheet = el("div", "sheet");
      var canvas = el("canvas");
      sheet.append(canvas);
      li.append(sheet, el("div", "num", T.page + " " + (i + 1)));
      grid.append(li);
      return doc.getPage(p.n + 1).then(function (page) {
        return drawPage(page, canvas, 150);
      });
    });
    // Rendered in order but without blocking: a 200 page file still shows
    // its first thumbnails straight away.
    return jobs.reduce(function (chain, job) {
      return chain.then(function () { return job; });
    }, Promise.resolve());
  }

  function cardControls(kind) {
    if (kind === "none") return;              // preview only, nothing to press
    var grid = $("#grid");
    Array.prototype.forEach.call(grid.children, function (li, i) {
      var acts = el("div", "acts");
      if (kind === "organize") {
        acts.append(
          btn("←", T.move_left, function () { move(i, -1); }),
          btn("↻", T.rotate, function () { rotate(i); }),
          btn("→", T.move_right, function () { move(i, 1); })
        );
      } else {
        acts.append(btn("✕", T.remove, function () { toggleKeep(i); }));
      }
      li.querySelector(".sheet").append(acts);
    });
    refresh();
  }
  function btn(label, title, fn) {
    var b = el("button", null, label);
    b.type = "button";
    b.title = title;
    b.setAttribute("aria-label", title);
    b.addEventListener("click", fn);
    return b;
  }

  function move(i, by) {
    var j = i + by;
    if (j < 0 || j >= state.pages.length) return;
    var tmp = state.pages[i];
    state.pages[i] = state.pages[j];
    state.pages[j] = tmp;
    var grid = $("#grid"), a = grid.children[i], b = grid.children[j];
    if (by < 0) grid.insertBefore(a, b); else grid.insertBefore(b, a);
    reindex();
    refresh();
  }
  function rotate(i) {
    state.pages[i].rot = (state.pages[i].rot + 90) % 360;
    refresh();
  }
  function toggleKeep(i) {
    state.pages[i].keep = !state.pages[i].keep;
    refresh();
  }
  function reindex() {
    Array.prototype.forEach.call($("#grid").children, function (li, i) {
      li.dataset.i = i;
      li.querySelector(".num").textContent = T.page + " " + (i + 1);
      var acts = li.querySelectorAll(".acts button");
      if (acts.length === 3) {
        acts[0].onclick = function () { move(i, -1); };
        acts[1].onclick = function () { rotate(i); };
        acts[2].onclick = function () { move(i, 1); };
      } else if (acts.length === 1) {
        acts[0].onclick = function () { toggleKeep(i); };
      }
    });
  }
  function refresh() {
    var kept = 0;
    Array.prototype.forEach.call($("#grid").children, function (li, i) {
      var p = state.pages[i];
      li.classList.toggle("gone", !p.keep);
      var c = li.querySelector("canvas");
      if (c) c.style.transform = "rotate(" + p.rot + "deg) scale(" + (p.rot % 180 ? 0.72 : 1) + ")";
      var first = li.querySelector(".acts button");
      if (first && li.querySelectorAll(".acts button").length === 3) {
        li.querySelectorAll(".acts button")[0].disabled = i === 0;
        li.querySelectorAll(".acts button")[2].disabled = i === state.pages.length - 1;
      }
      if (p.keep) kept++;
    });
    ready(kept > 0, T.n_pages.replace("{0}", kept));
  }

  // -- 1. merge -------------------------------------------------------------
  function initMerge() {
    wireDrop(function (files) {
      files.forEach(function (f) {
        if (/\.pdf$/i.test(f.name)) state.files.push(f);
      });
      if (!state.files.length) { say(T.err_not_pdf, "bad"); return; }
      listFiles();
    });
    function listFiles() {
      var ul = $("#files");
      ul.innerHTML = "";
      ul.hidden = false;
      state.files.forEach(function (f, i) {
        var li = el("li", "file");
        li.append(el("span", "nm", f.name), el("span", "sz", size(f.size)));
        li.append(
          btn("↑", T.move_up, function () { swap(i, -1); }),
          btn("↓", T.move_down, function () { swap(i, 1); }),
          btn("✕", T.remove, function () { state.files.splice(i, 1); listFiles(); })
        );
        li.querySelectorAll("button")[0].disabled = i === 0;
        li.querySelectorAll("button")[1].disabled = i === state.files.length - 1;
        ul.append(li);
      });
      ready(state.files.length >= 2,
            state.files.length < 2 ? T.need_two : T.n_files.replace("{0}", state.files.length));
    }
    function swap(i, by) {
      var j = i + by;
      if (j < 0 || j >= state.files.length) return;
      var t = state.files[i];
      state.files[i] = state.files[j];
      state.files[j] = t;
      listFiles();
    }
    $("#go").addEventListener("click", function () {
      busy(true);
      say(T.working);
      pdflib()
        .then(function (lib) { return lib.PDFDocument.create(); })
        .then(function (out) {
          return state.files.reduce(function (chain, f) {
            return chain.then(function () {
              return read(f).then(loadPdf).then(function (src) {
                return out.copyPages(src, src.getPageIndices()).then(function (pages) {
                  pages.forEach(function (p) { out.addPage(p); });
                });
              });
            });
          }, Promise.resolve()).then(function () { return out.save(); });
        })
        .then(function (bytes) {
          busy(false);
          say(T.done, "ok");
          results(T.done_title, T.done_merge,
                  [offer(new Blob([bytes], { type: "application/pdf" }), "merged.pdf")]);
        })
        .catch(fail);
    });
  }

  // -- 2. split -------------------------------------------------------------
  function initSplit() {
    var mode = "range";
    wireDrop(function (files) {
      takeOnePdf(files, function () {
        cardControls("none");
        $("#range").placeholder = "1-" + state.pages.length;
        ready(true, T.n_pages_doc.replace("{0}", state.pages.length));
      });
    });
    Array.prototype.forEach.call($("#mode").children, function (b) {
      b.addEventListener("click", function () {
        mode = b.dataset.mode;
        Array.prototype.forEach.call($("#mode").children, function (o) {
          o.setAttribute("aria-pressed", String(o === b));
        });
        $("#range-row").hidden = mode !== "range";
      });
    });
    $("#go").addEventListener("click", function () {
      busy(true);
      say(T.working);
      var total = state.pages.length;
      var wanted;
      try {
        wanted = mode === "range" ? parseRange($("#range").value || ("1-" + total), total) : null;
      } catch (e) { return fail(e); }
      if (wanted && !wanted.length) return fail(new Error(T.err_no_pages));

      loadPdf(state.bytes)
        .then(function (src) {
          return pdflib().then(function (lib) {
            if (mode === "range") {
              return lib.PDFDocument.create().then(function (out) {
                return out.copyPages(src, wanted).then(function (ps) {
                  ps.forEach(function (p) { out.addPage(p); });
                  return out.save();
                });
              }).then(function (bytes) {
                return [{ name: state.name + "-pages.pdf", data: bytes }];
              });
            }
            // one file per page
            return src.getPageIndices().reduce(function (chain, idx) {
              return chain.then(function (acc) {
                return lib.PDFDocument.create().then(function (out) {
                  return out.copyPages(src, [idx]).then(function (ps) {
                    out.addPage(ps[0]);
                    return out.save();
                  });
                }).then(function (bytes) {
                  acc.push({ name: state.name + "-" + String(idx + 1).padStart(3, "0") + ".pdf",
                             data: bytes });
                  return acc;
                });
              });
            }, Promise.resolve([]));
          });
        })
        .then(function (outs) {
          busy(false);
          say(T.done, "ok");
          if (outs.length === 1) {
            results(T.done_title, T.done_split,
                    [offer(new Blob([outs[0].data], { type: "application/pdf" }), outs[0].name)]);
          } else {
            results(T.done_title, T.done_split_many.replace("{0}", outs.length),
                    [offer(zip(outs), state.name + "-pages.zip")]);
          }
        })
        .catch(fail);
    });
  }

  // -- 3. organize (rotate + reorder) ---------------------------------------
  function initOrganize() {
    wireDrop(function (files) {
      takeOnePdf(files, function () { cardControls("organize"); });
    });
    $("#rot-all").addEventListener("click", function () {
      state.pages.forEach(function (p) { p.rot = (p.rot + 90) % 360; });
      refresh();
    });
    $("#go").addEventListener("click", function () {
      busy(true);
      say(T.working);
      loadPdf(state.bytes)
        .then(function (src) {
          return pdflib().then(function (lib) {
            return lib.PDFDocument.create().then(function (out) {
              var order = state.pages.map(function (p) { return p.n; });
              return out.copyPages(src, order).then(function (ps) {
                ps.forEach(function (p, i) {
                  var turn = state.pages[i].rot;
                  if (turn) {
                    p.setRotation(lib.degrees((p.getRotation().angle + turn) % 360));
                  }
                  out.addPage(p);
                });
                return out.save();
              });
            });
          });
        })
        .then(function (bytes) {
          busy(false);
          say(T.done, "ok");
          results(T.done_title, T.done_organize,
                  [offer(new Blob([bytes], { type: "application/pdf" }),
                         state.name + "-organized.pdf")]);
        })
        .catch(fail);
    });
  }

  // -- 4. delete pages ------------------------------------------------------
  function initDelete() {
    wireDrop(function (files) {
      takeOnePdf(files, function () { cardControls("delete"); });
    });
    $("#go").addEventListener("click", function () {
      var keep = state.pages.filter(function (p) { return p.keep; }).map(function (p) { return p.n; });
      if (!keep.length) return fail(new Error(T.err_all_gone));
      busy(true);
      say(T.working);
      loadPdf(state.bytes)
        .then(function (src) {
          return pdflib().then(function (lib) {
            return lib.PDFDocument.create().then(function (out) {
              return out.copyPages(src, keep).then(function (ps) {
                ps.forEach(function (p) { out.addPage(p); });
                return out.save();
              });
            });
          });
        })
        .then(function (bytes) {
          busy(false);
          say(T.done, "ok");
          results(T.done_title,
                  T.done_delete.replace("{0}", state.pages.length - keep.length),
                  [offer(new Blob([bytes], { type: "application/pdf" }),
                         state.name + "-trimmed.pdf")]);
        })
        .catch(fail);
    });
  }

  // -- 5. images to PDF -----------------------------------------------------
  function initImages() {
    var fit = "fit";
    wireDrop(function (files) {
      files.forEach(function (f) {
        if (/^image\/(jpeg|png)$/.test(f.type) || /\.(jpe?g|png)$/i.test(f.name)) {
          state.files.push(f);
        }
      });
      if (!state.files.length) { say(T.err_not_image, "bad"); return; }
      $("#ctl").hidden = false;
      listImages();
    });
    function listImages() {
      var grid = $("#grid");
      grid.innerHTML = "";
      grid.hidden = false;
      state.files.forEach(function (f, i) {
        var li = el("li", "card");
        var sheet = el("div", "sheet");
        var img = el("img", "thumb");
        img.alt = f.name;
        img.src = URL.createObjectURL(f);
        img.onload = function () { URL.revokeObjectURL(img.src); };
        sheet.append(img);
        var acts = el("div", "acts");
        acts.append(
          btn("←", T.move_left, function () { swap(i, -1); }),
          btn("✕", T.remove, function () { state.files.splice(i, 1); listImages(); }),
          btn("→", T.move_right, function () { swap(i, 1); })
        );
        acts.children[0].disabled = i === 0;
        acts.children[2].disabled = i === state.files.length - 1;
        sheet.append(acts);
        li.append(sheet, el("div", "num", f.name));
        grid.append(li);
      });
      ready(state.files.length > 0, T.n_images.replace("{0}", state.files.length));
    }
    function swap(i, by) {
      var j = i + by;
      if (j < 0 || j >= state.files.length) return;
      var t = state.files[i];
      state.files[i] = state.files[j];
      state.files[j] = t;
      listImages();
    }
    Array.prototype.forEach.call($("#fit").children, function (b) {
      b.addEventListener("click", function () {
        fit = b.dataset.fit;
        Array.prototype.forEach.call($("#fit").children, function (o) {
          o.setAttribute("aria-pressed", String(o === b));
        });
      });
    });
    $("#go").addEventListener("click", function () {
      busy(true);
      say(T.working);
      pdflib()
        .then(function (lib) {
          return lib.PDFDocument.create().then(function (out) {
            return state.files.reduce(function (chain, f) {
              return chain.then(function () {
                return read(f).then(function (bytes) {
                  var png = /\.png$/i.test(f.name) || f.type === "image/png";
                  return (png ? out.embedPng(bytes) : out.embedJpg(bytes));
                }).then(function (img) {
                  if (fit === "image") {
                    var p = out.addPage([img.width, img.height]);
                    p.drawImage(img, { x: 0, y: 0, width: img.width, height: img.height });
                    return;
                  }
                  // A4 with a 36 pt margin, portrait or landscape to suit
                  var wide = img.width > img.height;
                  var pw = wide ? 841.89 : 595.28, ph = wide ? 595.28 : 841.89;
                  var page = out.addPage([pw, ph]);
                  var m = 36;
                  var s = Math.min((pw - 2 * m) / img.width, (ph - 2 * m) / img.height);
                  var w = img.width * s, h = img.height * s;
                  page.drawImage(img, { x: (pw - w) / 2, y: (ph - h) / 2, width: w, height: h });
                });
              });
            }, Promise.resolve()).then(function () { return out.save(); });
          });
        })
        .then(function (bytes) {
          busy(false);
          say(T.done, "ok");
          results(T.done_title, T.done_images,
                  [offer(new Blob([bytes], { type: "application/pdf" }), "images.pdf")]);
        })
        .catch(fail);
    });
  }

  // -- 6. PDF to image ------------------------------------------------------
  function initToImage() {
    var format = "jpeg";
    wireDrop(function (files) {
      takeOnePdf(files, function () {
        cardControls("delete");
        ready(true, T.n_pages_doc.replace("{0}", state.pages.length));
      });
    });
    Array.prototype.forEach.call($("#fmt").children, function (b) {
      b.addEventListener("click", function () {
        format = b.dataset.fmt;
        Array.prototype.forEach.call($("#fmt").children, function (o) {
          o.setAttribute("aria-pressed", String(o === b));
        });
      });
    });
    $("#go").addEventListener("click", function () {
      var keep = state.pages.filter(function (p) { return p.keep; });
      if (!keep.length) return fail(new Error(T.err_all_gone));
      busy(true);
      say(T.working);
      var dpi = parseInt($("#dpi").value, 10) || 150;
      var scale = dpi / 72;
      var mime = format === "png" ? "image/png" : "image/jpeg";
      var ext = format === "png" ? "png" : "jpg";

      keep.reduce(function (chain, p, i) {
        return chain.then(function (acc) {
          say(T.rendering.replace("{0}", i + 1).replace("{1}", keep.length));
          return state.doc.getPage(p.n + 1).then(function (page) {
            var vp = page.getViewport({ scale: scale });
            var canvas = document.createElement("canvas");
            canvas.width = Math.floor(vp.width);
            canvas.height = Math.floor(vp.height);
            var ctx = canvas.getContext("2d");
            if (format !== "png") {                 // JPEG has no transparency
              ctx.fillStyle = "#ffffff";
              ctx.fillRect(0, 0, canvas.width, canvas.height);
            }
            return page.render({ canvasContext: ctx, viewport: vp }).promise.then(function () {
              return new Promise(function (ok) {
                canvas.toBlob(function (b) { ok(b); }, mime, 0.92);
              });
            });
          }).then(function (blob) {
            return blob.arrayBuffer().then(function (buf) {
              acc.push({ name: state.name + "-" + String(p.n + 1).padStart(3, "0") + "." + ext,
                         data: new Uint8Array(buf) });
              return acc;
            });
          });
        });
      }, Promise.resolve([]))
        .then(function (outs) {
          busy(false);
          say(T.done, "ok");
          if (outs.length === 1) {
            results(T.done_title, T.done_image_one,
                    [offer(new Blob([outs[0].data], { type: mime }), outs[0].name)]);
          } else {
            results(T.done_title, T.done_image_many.replace("{0}", outs.length),
                    [offer(zip(outs), state.name + "-" + ext + ".zip")]);
          }
        })
        .catch(fail);
    });
  }

  // ------------------------------------------------------------------- boot
  var starters = {
    "merge-pdf": initMerge,
    "split-pdf": initSplit,
    "organize-pdf": initOrganize,
    "delete-pages": initDelete,
    "images-to-pdf": initImages,
    "pdf-to-image": initToImage
  };
  if (starters[TOOL]) starters[TOOL]();

  // Theme, shared with the rest of the site.
  (function () {
    var root = document.documentElement, button = $("#theme");
    function paintTheme(mode) {
      root.setAttribute("data-theme", mode);
      $("#i-sun", button).style.display = mode === "dark" ? "" : "none";
      $("#i-moon", button).style.display = mode === "dark" ? "none" : "";
    }
    var chosen = null;
    try { chosen = localStorage.getItem("theme"); } catch (e) {}
    paintTheme(chosen || "light");
    button.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      paintTheme(next);
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
  })();

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      // Registered per language, because a worker can only claim pages at
      // or below its own path.
      var sw = document.body.dataset.sw || "./sw.js";
      navigator.serviceWorker.register(sw).catch(function () {});
    });
  }
})();
