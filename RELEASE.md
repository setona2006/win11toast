## リリース手順

このリポジトリはタグ `v*` をプッシュすると GitHub Actions が ZIP を作成し、リリースに添付します。

### 事前チェック
- ローカルで仮想環境を有効化し、アプリ起動・POSTテストが通ること
- CI がグリーン（`Actions` タブで確認）

### バージョンタグの付与とプッシュ
```powershell
git pull origin main
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

### 生成物
- `dist/win11toast.zip` が GitHub Release のアセットとして添付されます
  - `README.md`
  - `requirements.txt`
  - `ucar_rt_listener.py`

### 運用メモ
- CIでは環境変数 `UCAR_DISABLE_TOAST=1` を設定し、トースト通知を抑止しています
- ローカル検証時もトーストを無効化したい場合は環境変数を設定してください
  - PowerShell: `$env:UCAR_DISABLE_TOAST = '1'`
  - 解除: `Remove-Item Env:\UCAR_DISABLE_TOAST`


