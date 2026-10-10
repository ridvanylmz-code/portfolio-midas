/* Midas kasası: şifreli portföy dosyalarını tarayıcıda açar (WebCrypto, sunucuya hiçbir şey gitmez).
   Biçim scripts/common.py vault_encrypt ile aynı: {"vault":1, "iter", "salt", "iv", "data"}
   AES-256-GCM, anahtar = PBKDF2-SHA256(parola, salt, iter). Parola GitHub secret PORTFOLIO_KEY ile aynıdır.
   Parola yalnızca bu cihazda tutulur: oturum boyunca bellekte, "Bu cihazda hatırla" seçilirse localStorage'da. */
(function () {
  "use strict";
  var LS = "pm_vault_pw";
  var mem = null, asking = null, keys = {};

  function lsGet() { try { return localStorage.getItem(LS) } catch (e) { return null } }
  function lsSet(v) { try { v ? localStorage.setItem(LS, v) : localStorage.removeItem(LS) } catch (e) {} }
  function isVault(o) { return !!(o && o.vault === 1 && o.data && o.salt && o.iv) }
  function b64(s) { var b = atob(s), u = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u }

  function deriveKey(pw, salt, iter) {
    var id = pw.length + ":" + salt + ":" + iter + ":" + pw;
    if (!keys[id]) {
      keys[id] = crypto.subtle.importKey("raw", new TextEncoder().encode(pw), "PBKDF2", false, ["deriveKey"])
        .then(function (base) {
          return crypto.subtle.deriveKey({ name: "PBKDF2", hash: "SHA-256", salt: b64(salt), iterations: iter },
            base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
        });
      keys[id].catch(function () { delete keys[id] });
    }
    return keys[id];
  }

  function decrypt(env, pw) {
    return deriveKey(pw, env.salt, +env.iter || 600000).then(function (k) {
      return crypto.subtle.decrypt({ name: "AES-GCM", iv: b64(env.iv) }, k, b64(env.data));
    }).then(function (buf) { return JSON.parse(new TextDecoder().decode(buf)) });
  }

  /* ---- parola ekranı ---- */
  function css() {
    if (document.getElementById("vault-css")) return;
    var s = document.createElement("style"); s.id = "vault-css";
    s.textContent =
      "#vault{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;" +
      "background:rgba(6,8,13,.86);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);" +
      "font:15px/1.4 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#e8ecf4}" +
      "#vault .vc{width:100%;max-width:340px;background:#121722;border:1px solid #263042;border-radius:18px;padding:22px 20px;box-shadow:0 20px 60px rgba(0,0,0,.5)}" +
      "#vault h2{margin:0 0 6px;font-size:18px;letter-spacing:.02em}" +
      "#vault p{margin:0 0 14px;color:#9aa6ba;font-size:13px}" +
      "#vault input[type=password]{width:100%;box-sizing:border-box;padding:12px 14px;border-radius:12px;border:1px solid #2c3850;" +
      "background:#0b0f17;color:#fff;font-size:16px;outline:none}" +
      "#vault input[type=password]:focus{border-color:#4f7cff}" +
      "#vault label{display:flex;gap:8px;align-items:center;margin:12px 0 14px;color:#b9c3d4;font-size:13px}" +
      "#vault button{width:100%;padding:12px;border:0;border-radius:12px;background:#3d6bff;color:#fff;font-weight:600;font-size:15px;cursor:pointer}" +
      "#vault button:disabled{opacity:.6}" +
      "#vault .ve{min-height:18px;margin-top:10px;color:#ff8a94;font-size:13px}";
    document.head.appendChild(s);
  }

  function ask(msg) {
    if (asking) return asking;
    css();
    asking = new Promise(function (resolve) {
      var w = document.createElement("div"); w.id = "vault";
      w.innerHTML = '<form class="vc" autocomplete="on"><h2>🔒 Portföy kilitli</h2>' +
        '<p>Adet, maliyet ve işlemler şifreli. Parolanı gir (GitHub\'daki PORTFOLIO_KEY).</p>' +
        '<input type="text" name="username" value="midas" autocomplete="username" hidden>' +
        '<input type="password" autocomplete="current-password" placeholder="Parola" required>' +
        '<label><input type="checkbox" checked> Bu cihazda hatırla</label>' +
        '<button type="submit">Aç</button><div class="ve"></div></form>';
      document.body.appendChild(w);
      var f = w.querySelector("form"), inp = w.querySelector("input[type=password]"),
        rem = w.querySelector("input[type=checkbox]"), err = w.querySelector(".ve");
      err.textContent = msg || "";
      setTimeout(function () { inp.focus() }, 50);
      f.onsubmit = function (e) {
        e.preventDefault();
        var pw = inp.value;
        if (!pw) return;
        w.remove(); asking = null;
        resolve({ pw: pw, remember: rem.checked });
      };
    });
    return asking;
  }

  var trial = null; // aynı anda açılan dosyalar tek parola denemesini paylaşsın
  function open(env) {
    if (!isVault(env)) return Promise.resolve(env);
    function attempt(pw, remember, msg) {
      var p = pw ? Promise.resolve({ pw: pw, remember: remember }) : ask(msg);
      return p.then(function (c) {
        return decrypt(env, c.pw).then(function (obj) {
          mem = c.pw;
          if (c.remember) lsSet(c.pw);
          return obj;
        }, function () {
          if (mem === c.pw) mem = null;
          if (lsGet() === c.pw) lsSet(null);
          return attempt(null, false, "Parola yanlış, tekrar dene.");
        });
      });
    }
    if (mem) return attempt(mem, false);
    var stored = lsGet();
    if (stored) return attempt(stored, true);
    if (!trial) {
      trial = attempt(null, false).then(function (o) { trial = null; return o }, function (e) { trial = null; throw e });
      return trial;
    }
    return trial.then(function () { return attempt(mem, false) });
  }

  function forget() { mem = null; keys = {}; lsSet(null); location.reload() }

  window.Vault = { isVault: isVault, open: open, forget: forget,
    unlocked: function () { return !!mem } };
})();
