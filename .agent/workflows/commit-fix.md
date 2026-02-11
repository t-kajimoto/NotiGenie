---
description: 変更をコミットしてプッシュする
---

// turbo-all

1. 変更状況を確認する

```
git status --short
```

2. 変更内容を確認し、論理的な単位でステージングしてコミットする

- 関連するファイルをまとめて `git add` する
- conventional commits 形式でコミットメッセージを書く
- プレフィックス例: `feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`
- スコープは任意: `feat(cloud_functions):`, `fix(raspberry_pi):`
- **重要: コミットメッセージは必ず日本語で書くこと**
- 例: `refactor(cloud_functions): DB選択ステップを削除し、統合DBに移行`

3. **プッシュはしない。** ユーザーが明示的に指示した場合のみプッシュする。
