# Balanceador de carga - MC714

Simulador de um balanceador de carga para três servidores, desenvolvido em
Python e SimPy para o Trabalho 1 de MC714 - Sistemas Distribuídos da UNICAMP.

O enunciado vigente é `MC714_enunciado.pdf`. Em pontos de divergência, ele
substitui a versão antiga `MC714_2s2026.pdf`. O roteiro atualizado está em
[PLANO_IMPLEMENTACAO.md](PLANO_IMPLEMENTACAO.md).

## Objetivo vigente

O sistema final terá:

- chegadas Poisson;
- 3 servidores homogêneos com uma unidade de processamento cada;
- filas FCFS ilimitadas;
- tempos de serviço exponenciais com `mu=1` e média 1;
- políticas Aleatória, Round Robin e Fila Mais Curta;
- execuções de 5000 unidades, descartando as primeiras 500 como warm-up;
- métricas de vazão, resposta, número médio no sistema e utilização;
- comparação com o modelo analítico `M/M/1` da política Aleatória.

## Estado atual

Já estão implementados:

- `SimulationConfig` imutável e validada;
- `Request` e seu ciclo de vida;
- `Server` com `simpy.Resource`, fila FIFO e histórico de estados;
- `MetricsCollector`, `RunMetrics` e eventos imutáveis;
- invariantes de topologia, capacidade, eventos e conservação;
- logs estruturados de configuração, eventos e resumo;
- `LoadBalancer`;
- políticas Aleatória, Round Robin e Fila Mais Curta;
- gerador de chegadas Poisson reproduzível;
- testes unitários e testes parciais de integração;
- notebooks de configuração e integração.

Em 8 de setembro de 2026, a suíte possui **119 testes aprovados**.

## Alinhamentos ainda necessários

O código ainda conserva alguns padrões do enunciado antigo:

- capacidade padrão 15 em vez de 1;
- serviço constante de 0,05 em vez de exponencial com média 1;
- horizonte 200 em vez de 5000;
- ausência de warm-up de 500 unidades;
- Fila Mais Curta sem desempate aleatório.

Também faltam:

- integração pública dos eventos do servidor com o coletor, sem monkey patch;
- cálculo temporal de `E[N]` e utilização por servidor;
- executor completo de uma rodada;
- executor das 150 rodadas estáveis;
- modelo analítico `M/M/1`;
- experimento instável com `lambda=3,3`;
- intervalos de confiança, CSVs, gráficos e CLI.

O gerador Poisson já está alinhado ao novo enunciado. Pareto Limitada, Hurst e
rajadas de 30 a 120 não fazem mais parte dos requisitos vigentes.

## Componentes

| Componente | Responsabilidade |
| --- | --- |
| `SimulationConfig` | Configura e valida uma rodada. Seus padrões ainda serão atualizados. |
| `Request` | Mantém IDs, chegada, atribuição, início, conclusão e tempos derivados. |
| `Server` | Processa requisições, mantém fila FIFO e registra estados. |
| `ServerState` | Fotografia imutável do estado de um servidor. |
| `LoadBalancer` | Seleciona um servidor pela política e inicia o atendimento. |
| `RandomPolicy` | Escolhe um servidor pseudoaleatoriamente. |
| `RoundRobinPolicy` | Distribui requisições ciclicamente. |
| `ShortestQueuePolicy` | Escolhe a menor ocupação; o desempate ainda será ajustado. |
| `PoissonTrafficGenerator` | Produz chegadas Poisson no ambiente SimPy. |
| `MetricsCollector` | Preserva eventos e calcula as métricas atualmente disponíveis. |
| `RunMetrics` | Resumo imutável de uma rodada. |
| `SimulationLogger` | Emite configuração, eventos e resumo. |
| `validate_simulation_invariants` | Valida topologia, ciclos de vida e conservação. |

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

## Testes

Com o ambiente virtual ativado:

```bash
pytest
```

Os testes usam somente o relógio simulado do SimPy e não dependem de espera em
tempo real.

## Estrutura atual

```text
src/load_balancer_sim/
├── __init__.py
├── config.py
├── invariants.py
├── load_balancer.py
├── logs.py
├── metrics.py
├── request.py
├── server.py
└── traffic.py

tests/
├── test_config.py
├── test_environment.py
├── test_invariants.py
├── test_load_balancer.py
├── test_logs.py
├── test_metrics.py
├── test_request.py
├── test_server.py
└── test_traffic.py
```

Os notebooks em `notebooks/` são materiais auxiliares. O fluxo definitivo da
simulação deve residir nos módulos do pacote, sem acessar atributos privados.

## Próximo commit técnico

O próximo marco recomendado é atualizar a configuração e o servidor para o
serviço exponencial:

```text
server_capacity = 1
service_rate = 1.0
service_duration ~ Exponencial(service_rate)
horizon = 5000
warmup = 500
```

Os testes do servidor devem poder injetar durações determinísticas, enquanto a
simulação real usa amostras exponenciais reproduzíveis.
