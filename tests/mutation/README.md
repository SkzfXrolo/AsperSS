# Mutation testing (mutmut)

## Ejecutar

```bash
python -m pip install -r tests/requirements-test.txt
mutmut run --paths-to-mutate web_app/argus_ai_oracle.py
mutmut run --paths-to-mutate web_app/argus_ai_features.py
mutmut run --paths-to-mutate web_app/argus_ai_trainer.py
mutmut run --paths-to-mutate web_app/argus_ai_labeler.py
mutmut run --paths-to-mutate web_app/argus_ai_assistant.py
```

O usar wrapper:

```bash
bash scripts/test/run-mutation.sh
```

## Ver resultados

```bash
mutmut results
mutmut show <id>
```

Target recomendado: **mutation score > 70%**.
