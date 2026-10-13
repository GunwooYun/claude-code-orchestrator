# Known Pitfalls — measured facts only

**규칙**: 여기에는 **직접 측정해서 확인한 사실만** 적는다. 모델이 이미 아는 일반
지식은 적지 않는다 — 스택별 레시피 파일은 의도적으로 만들지 않았다. 낡은 레시피를
모델이 자기 지식보다 신뢰하면 레시피가 없는 것보다 나쁘다.

각 항목은 **사실 / 측정 방법 / 측정 날짜**를 갖는다. 날짜 없는 항목은 지운다.

`/initproject` 가 스택을 감지한 뒤 이 파일에서 해당 항목을 찾는다. 감지된 스택에
대한 항목이 없으면 이 파일은 아무 말도 하지 않는다 — 그때는 모델 자신의 지식으로
판단하고, 확신이 없으면 agy 에 T3 질의를 한 번 한다.

---

## 포맷터: "설치돼 있다"와 "채택했다"는 다르다

**사실** — 포맷터가 설치돼 있어도 저장소가 그 스타일을 따르지 않을 수 있다.
예전 템플릿의 저장 훅은 black 을 정해 두고 파일을 제자리에서 고쳐 썼다. 그
훅을 쓰던 프로젝트는 black 설정 파일이 없었고, 추적되는 Python 파일 555개 중
414개(약 75%)가 `black --check` 에서 "would reformat" 으로 나왔다.

이런 저장소에 서식 검사를 저장 티어에 넣으면, 손대지 않은 코드까지 저장할 때마다
실패로 보고된다. 고쳐 쓰게 하면 이전 작성자가 일부러 열 맞춰 정렬한 주석이 깨진다.
서식 검사는 겉모양만 판정하고, 로직에는 영향이 없다.

**측정 방법** — 저장소 루트에서 `uvx black --check $(git ls-files '*.py')` 를
실행해 마지막 줄의 "N files would be reformatted, M files would be left
unchanged" 를 읽었다. 설정 파일은 `pyproject.toml` 의 `[tool.black]` 유무로
확인했다.

**측정 날짜** — 2026-10-07

## 타입체커를 고를 때: ORM/프레임워크의 디스크립터

**사실** — Django 모델을 `ty` 로 검사하면 **정상 코드가 오탐으로 잡힌다.**
`ty` 에는 플러그인 개념이 없어서 `models.CharField` 를 디스크립터로 해석하지
못하고 필드 객체 그대로 본다. 그래서 모델 필드를 만지는 모든 줄이 에러가 된다.
`mypy` + `django-stubs` 는 같은 코드에서 깨끗하다.

**측정 방법** — 정상인 코드 3줄로 두 도구를 비교했다.

```python
class Article(models.Model):
    title = models.CharField(max_length=100)
    views = models.IntegerField(default=0)

def correct_title(a: Article) -> str:  return a.title          # 정상
def correct_upper(a: Article) -> str:  return a.title.upper()  # 정상
def correct_math(a: Article) -> int:   return a.views + 1      # 정상
```

```
mypy + django-stubs   Success: no issues found
ty                    error[invalid-return-type]   expected `str`, found `CharField`
                      error[unresolved-attribute]  `CharField` has no attribute `upper`
                      error[unsupported-operator]  Unsupported `+` operation
```

**날짜** — 2026-09-25 (`ty` 0.0.84, `mypy` 1.19.1, django-stubs)

**일반화** — 이 함정은 Django 고유가 아니라 **디스크립터나 메타클래스로 속성
타입을 바꾸는 모든 프레임워크**에 적용된다. 그런 프레임워크를 쓰는 프로젝트에서는
플러그인을 지원하는 타입체커를 고른다. 순수 라이브러리 코드라면 해당 없다.

---

## `ty` 는 애노테이션 누락을 검사하지 않는다

**사실** — `ty` 에는 `mypy` 의 `disallow_untyped_defs` 에 해당하는 기능이 없다.
`--error all` 로도 잡히지 않는다. "모든 함수에 타입 애노테이션 필수" 규칙을
`ty` 로 강제할 수 없다.

**우회** — `ruff` 의 `ANN` 규칙셋(flake8-annotations)이 정확히 이것을 잡는다.
`ty` 를 쓰는 프로젝트에서 애노테이션 강제가 필요하면 `select` 에 `ANN` 을 넣는다.

**측정 방법** — 애노테이션 없는 함수를 두 도구와 `ruff --select ANN` 에 넣었다.
`ty` 는 `--error all` 에서도 0건, `mypy --strict` 와 `ruff ANN` 은 검출.

**날짜** — 2026-09-25
