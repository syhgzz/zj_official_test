window.PRECIP_DATA = {
  "generatedAt": "2026-09-10 16:37:33",
  "date": "2026-08-28",
  "hourRange": [
    0,
    12
  ],
  "requestBbox": [
    115.328154013575,
    39.37649512177754,
    117.62405180611998,
    41.097765196719216
  ],
  "engine": {
    "name": "wcontour-1.6.1-port",
    "bandMode": "auto",
    "referenceSize": 256
  },
  "layers": {
    "XTSKJSXS": {
      "name": "小时降水量",
      "unit": "mm",
      "metric": "rain",
      "breaks": [
        0.0,
        0.1,
        1.6,
        7.0,
        15.0,
        40.0,
        50.0
      ],
      "colors": [
        "#FCFCFC00",
        "#34E498",
        "#24B458",
        "#4880E8",
        "#243CD4",
        "#D81CC4",
        "#98002C"
      ],
      "legendLabels": [
        "0~0.1 零至小雨",
        "0.1~1.6 小雨",
        "1.6~7.0 中雨",
        "7.0~15.0 大雨",
        "15.0~40.0 暴雨",
        "40.0~50.0 大暴雨",
        "≥50.0 特大暴雨"
      ],
      "legendOrder": "asc",
      "algoParams": {
        "engine": "wcontour-1.6.1-port",
        "bandMode": "auto",
        "clip": false
      },
      "frames": [
        {
          "dtms": 1787886000000,
          "time": "2026-08-28 11:00",
          "items": {
            "xt": {
              "png": "layers/XTSKJSXS_1100_ref.png",
              "bbox": [
                115.328154013575,
                39.37649512177754,
                117.62405180611998,
                41.097765196719216
              ]
            },
            "xtWhite": {
              "png": "layers/XTSKJSXS_1100_ref_white.png",
              "bbox": [
                115.328154013575,
                39.37649512177754,
                117.62405180611998,
                41.097765196719216
              ]
            }
          },
          "inputMode": "grid",
          "scatterSource": null,
          "info": "接口格网 198x192 → 等值面 20 个（填色 20）",
          "stats": {
            "cols": 198,
            "rows": 192,
            "nPolygons": 20,
            "nDrawn": 20,
            "nNan": 0,
            "vmin": 0.0,
            "vmax": 11.264592440427277
          },
          "src": "降水页_降雨图层格网数据_降水量(小时)_XTSKJSXS_None_20260910_153138_api_v1_upns_precipitation_layers.json"
        },
        {
          "dtms": 1787889600000,
          "time": "2026-08-28 12:00",
          "items": {
            "xt": {
              "png": "layers/XTSKJSXS_1200_ref.png",
              "bbox": [
                115.328154013575,
                39.37649512177754,
                117.62405180611998,
                41.097765196719216
              ]
            },
            "xtWhite": {
              "png": "layers/XTSKJSXS_1200_ref_white.png",
              "bbox": [
                115.328154013575,
                39.37649512177754,
                117.62405180611998,
                41.097765196719216
              ]
            }
          },
          "inputMode": "grid",
          "scatterSource": null,
          "info": "接口格网 198x192 → 等值面 17 个（填色 17）",
          "stats": {
            "cols": 198,
            "rows": 192,
            "nPolygons": 17,
            "nDrawn": 17,
            "nNan": 0,
            "vmin": 0.0,
            "vmax": 6.7373265701856075
          },
          "src": "降水页_降雨图层格网数据_降水量(小时)_XTSKJSXS_None_20260910_153138_api_v1_upns_precipitation_layers.json"
        }
      ]
    }
  },
  "refs": [],
  "compareImages": []
};
