/**
 * Fechas de nacimiento: entrada manual en DD/MM/AAAA.
 * Al enviar, normaliza a DD/MM/AAAA para la BD (coherente con el código del portal).
 */
(function () {
  'use strict';

  function formatearDDMMYYYY(d) {
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yyyy = d.getFullYear();
    return dd + '/' + mm + '/' + yyyy;
  }

  function parseFechaDMY(s) {
    if (!s) return null;
    s = String(s).trim();
    if (!s) return null;
    var y, mo, d, dt, p, m2, only;
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
      p = s.split('-');
      y = parseInt(p[0], 10);
      mo = parseInt(p[1], 10) - 1;
      d = parseInt(p[2], 10);
      dt = new Date(y, mo, d);
      if (dt.getFullYear() !== y || dt.getMonth() !== mo || dt.getDate() !== d) return null;
      return dt;
    }
    m2 = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (m2) {
      d = parseInt(m2[1], 10);
      mo = parseInt(m2[2], 10) - 1;
      y = parseInt(m2[3], 10);
      dt = new Date(y, mo, d);
      if (dt.getFullYear() !== y || dt.getMonth() !== mo || dt.getDate() !== d) return null;
      return dt;
    }
    only = s.replace(/\D/g, '');
    if (only.length === 8) {
      d = parseInt(only.slice(0, 2), 10);
      mo = parseInt(only.slice(2, 4), 10) - 1;
      y = parseInt(only.slice(4, 8), 10);
      dt = new Date(y, mo, d);
      if (dt.getFullYear() !== y || dt.getMonth() !== mo || dt.getDate() !== d) return null;
      return dt;
    }
    return null;
  }

  function validarRangoFechaNac(fecha) {
    var hoy = new Date();
    var min = new Date(hoy.getFullYear() - 100, hoy.getMonth(), hoy.getDate());
    var max = new Date(hoy.getFullYear() - 1, hoy.getMonth(), hoy.getDate());
    return fecha >= min && fecha <= max;
  }

  function onInputFecha(e) {
    e.target.value = e.target.value.replace(/[^\d/]/g, '').slice(0, 10);
  }

  function onBlurFecha(e) {
    var el = e.target;
    var v = el.value.replace(/\D/g, '');
    if (v.length === 8) {
      el.value = v.slice(0, 2) + '/' + v.slice(2, 4) + '/' + v.slice(4, 8);
    }
    var dt = parseFechaDMY(el.value);
    if (!el.value.trim()) {
      el.setCustomValidity('');
      return;
    }
    if (!dt) {
      el.setCustomValidity('Use el formato DD/MM/AAAA (ej. 15/08/2010)');
      return;
    }
    if (!validarRangoFechaNac(dt)) {
      el.setCustomValidity('Fecha de nacimiento inv\u00E1lida');
      return;
    }
    el.setCustomValidity('');
  }

  function initFechasNacimientoInputs(root) {
    var scope = root || document;
    var inputs = scope.querySelectorAll('.fecha-nac-text');
    inputs.forEach(function (el) {
      el.setAttribute('autocomplete', 'bday');
      el.addEventListener('input', onInputFecha);
      el.addEventListener('blur', onBlurFecha);
    });
  }

  function normalizarFechasNacimientoEnFormulario(form) {
    if (!form) return true;
    var inputs = form.querySelectorAll('.fecha-nac-text');
    for (var i = 0; i < inputs.length; i++) {
      var el = inputs[i];
      var raw = el.value.trim();
      if (!raw) {
        el.value = '';
        el.setCustomValidity('');
        continue;
      }
      var dt = parseFechaDMY(raw);
      if (!dt) {
        el.setCustomValidity('Use el formato DD/MM/AAAA (ej. 15/08/2010)');
        el.reportValidity();
        el.focus();
        return false;
      }
      if (!validarRangoFechaNac(dt)) {
        el.setCustomValidity('Fecha de nacimiento inv\u00E1lida');
        el.reportValidity();
        el.focus();
        return false;
      }
      el.value = formatearDDMMYYYY(dt);
      el.setCustomValidity('');
    }
    return true;
  }

  window.parseFechaNacimientoPE = parseFechaDMY;
  window.initFechasNacimientoInputs = initFechasNacimientoInputs;
  window.normalizarFechasNacimientoEnFormulario = normalizarFechasNacimientoEnFormulario;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initFechasNacimientoInputs(document);
    });
  } else {
    initFechasNacimientoInputs(document);
  }
})();
