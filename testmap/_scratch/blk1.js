
/* 上面两行注入点在「单文件」产物里会被替换成真实数据；本模板里它们是注释，
   所以下面这份内嵌数据就是兜底。构建脚本会看注入点在不在：不在就说明数据
   已经烘进文件里了，直接原样输出，不再重复注入。 */
(function () {
  var baked = null;   /*{{SINGLE_HTML_BAKED_DATA}}*/
  var loaded = window.XT;
  if (loaded) delete window.XT;          /* 免得下面把外部数据又当成内嵌数据用 */
  window.__XT_SRC = 'none';
  try {
    if (loaded) {
      window.XT = loaded;
      window.__XT_SRC = 'external';
      /* 同目录那份可能是上一次构建留下的旧数据。比一下时间戳，别让旧数据
         盖掉更新的内嵌数据。 */
      if (baked && baked.frames && baked.frames.length) {
        var t1 = loaded.frames && loaded.frames.length
          ? loaded.frames[loaded.frames.length - 1].dtms : 0;
        var t2 = baked.frames[baked.frames.length - 1].dtms || 0;
        if (t2 > t1) { window.XT = baked; window.__XT_SRC = 'embedded-newer'; }
      }
    } else if (baked) {
      window.XT = baked;
      window.__XT_SRC = 'embedded';
    }
  } catch (e) {
    if (baked) { window.XT = baked; window.__XT_SRC = 'embedded-after-error'; }
  }
})();
