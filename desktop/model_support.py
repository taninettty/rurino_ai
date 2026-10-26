"""Check exported model dependencies before passing them to the native SDK."""
import json
from pathlib import Path, PureWindowsPath


def validate_model(filename):
    path = Path(filename).resolve()
    if not path.name.endswith('.model3.json'):
        raise ValueError('请选择 Cubism 导出的 .model3.json，PSD 和 .cmo3 不能直接运行。')
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        refs = data['FileReferences']
        if data['Version'] != 3 or not isinstance(refs, dict):
            raise ValueError()
        textures = refs['Textures']
        if not isinstance(textures, list) or not textures:
            raise ValueError()
        files = [refs['Moc'], *textures]
        files += [refs[key] for key in ('Physics', 'Pose', 'UserData', 'DisplayInfo') if refs.get(key)]
        for expression in refs.get('Expressions', []):
            files.append(expression['File'])
        for motions in refs.get('Motions', {}).values():
            for motion in motions:
                files.append(motion['File'])
                if motion.get('Sound'):
                    files.append(motion['Sound'])
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError('模型 JSON 格式错误，或缺少 Moc / Textures。请从 Cubism 重新完整导出。') from error
    for name in files:
        if not isinstance(name, str) or not name or '\\' in name or PureWindowsPath(name).drive:
            raise ValueError('模型资源应使用文件夹内的相对路径，并以 / 分隔。')
        asset = (path.parent / name).resolve()
        if Path(name).is_absolute() or not asset.is_relative_to(path.parent) or not asset.is_file():
            raise ValueError(f'模型资源缺失或越出模型文件夹：{name}\n请保留完整文件夹结构。')
    with (path.parent / refs['Moc']).open('rb') as stream:
        if stream.read(4) != b'MOC3':
            raise ValueError('Moc 文件不是 Cubism 导出的 MOC3 文件。')
    return path, data
