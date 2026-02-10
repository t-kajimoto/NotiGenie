---
description: Raspberry PiのCIエラー修正をコミットする
---

1. コードと依存関係の修正をコミット
   // turbo
   git add raspberry_pi/requirements.txt raspberry_pi/tts_factory.py
   git commit -m "fix(raspberry_pi): numpy依存の追加とTTSファクトリの修正"

2. テストコードの修正をコミット
   // turbo
   git add raspberry_pi/tests/test_aquestalk_client.py raspberry_pi/tests/test_tts_factory.py
   git commit -m "test(raspberry_pi): AquesTalkClientとTTSFactoryのテスト修正"

3. 変更をプッシュ
   // turbo
   git push origin main
