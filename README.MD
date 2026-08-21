# Balanceador de carga - MC714

Implementação do primeiro trabalho da disciplina MC714 - Sistemas Distribuídos
da UNICAMP.

O projeto simulará um balanceador de carga e três servidores com o SimPy. O
desenvolvimento está sendo feito em módulos pequenos e funcionais para facilitar
a divisão do trabalho da dupla e manter um histórico de commits legível.

## Requisitos

- Python 3.11 ou mais recente;
- `pip`.

## Preparação do ambiente

### Linux

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Windows PowerShell

```powershell
py -3 -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Verificação

Com o ambiente virtual ativado, execute:

```bash
pytest
```

Neste primeiro marco, o teste apenas verifica se o pacote pode ser importado e
se o relógio de eventos discretos do SimPy avança corretamente. Os componentes
de domínio serão adicionados em commits posteriores.

O roteiro completo está em [PLANO_IMPLEMENTACAO.md](PLANO_IMPLEMENTACAO.md).
