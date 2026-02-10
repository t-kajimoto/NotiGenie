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
- 例: `feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`
- スコープは任意: `feat(cloud_functions):`, `fix(raspberry_pi):`

3. リモートにプッシュする

```
git push origin main
```
