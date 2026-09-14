
/* 底图凭证与帧数据都优先用同目录的外部文件（HTTP 访问时），
   取不到就回落到下面内嵌的那份 —— 所以这个文件双击（file://）也能直接用。 */
(function () {
  if (window.WMTS_MAP_CONFIG) return;
  var s = document.createElement('script');
  s.src = './wmts_map_config.js';
  s.onerror = function () { window.WMTS_MAP_CONFIG = null; };
  document.head.appendChild(s);
})();
