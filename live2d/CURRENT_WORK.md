状态：原生MOC3已导出，7参数均有绑定；以下三命令退出码均为0（Linux/Xvfb，非Windows实测）。smoke开头异常是故意拒绝PNG的恢复测试；Level=Error是SDK日志级别。
```text
$ python -c "import sys;sys.path.insert(0,'desktop');from model_support import validate_model;print(validate_model(r'live2d/model/Rurino_Desktop.model3.json')[0])"
/home/vboxuser/Documents/ChatGPT/02/rurino_github_delivery/live2d/model/Rurino_Desktop.model3.json
$ python desktop/tests/smoke_live2d.py live2d/model/Rurino_Desktop.model3.json
ERROR:root:Model selection failed
Traceback (most recent call last):
  File "/home/vboxuser/Documents/ChatGPT/02/rurino_github_delivery/desktop/app.py", line 373, in load_model
    path, data = validate_model(filename)
                 ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/vboxuser/Documents/ChatGPT/02/rurino_github_delivery/desktop/model_support.py", line 9, in validate_model
    raise ValueError('请选择 Cubism 导出的 .model3.json，PSD 和 .cmo3 不能直接运行。')
ValueError: 请选择 Cubism 导出的 .model3.json，PSD 和 .cmo3 不能直接运行。
[95m────────────────────────────────────────────────[0m
  [93m★[0m [1m[96mlive2d-py[0m  [2m·[0m  [1mNon-official live2d library[0m
      [2mversion[0m  [92m[1m1.0.0[0m
      [2m CsmSDK[0m  [92m[1m5-r.5[0m
     [2mOfficial[0m  [92m[1mhttps://www.live2d.com/en/sdk/about/[0m
[95m────────────────────────────────────────────────[0m
PASS: setup, invalid-model recovery, real transparent rendering, audio envelope, mute, topmost, sizing, dragging, settings, reload, cleanup
[v3][I] [Pal] Init Shader Dir: /home/vboxuser/Documents/ChatGPT/02/rurino_desktop_pet/.venv/lib/python3.12/site-packages/live2d/
Live2D Cubism SDK Core Version 6.0.1
[v3][I] Load model: /home/vboxuser/Documents/ChatGPT/02/rurino_github_delivery/live2d/model/Rurino_Desktop.moc3
Live2D Cubism SDK Core Version 6.0.1
[v3][I] Load model: /home/vboxuser/Documents/ChatGPT/02/rurino_github_delivery/live2d/model/Rurino_Desktop.moc3
$ python desktop/tests/check_binding.py live2d/model/Rurino_Desktop.model3.json
ParamEyeLOpen: 已绑定（画面随参数变化） changed_pixels=5276
ParamEyeROpen: 已绑定（画面随参数变化） changed_pixels=5281
ParamMouthOpenY: 已绑定（画面随参数变化） changed_pixels=1169
ParamAngleX: 已绑定（画面随参数变化） changed_pixels=190236
ParamAngleY: 已绑定（画面随参数变化） changed_pixels=195150
ParamAngleZ: 已绑定（画面随参数变化） changed_pixels=281262
ParamBreath: 已绑定（画面随参数变化） changed_pixels=53633
PASS: all 7 required parameters change native rendered pixels
[pyi][E] [Log] Level=Error
Live2D Cubism SDK Core Version 6.0.1
```
下一步：Windows加载 live2d/model/Rurino_Desktop.model3.json；继续改善转头透视、后发与完整马尾美术。
