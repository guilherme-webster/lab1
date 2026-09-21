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
- `Server` com uma unidade de processamento, fila FIFO, serviço exponencial
  reproduzível, histórico de estados e callbacks públicos de serviço;
- configuração vigente com `service_rate=1`, horizonte 5000 e warm-up 500;
- `MetricsCollector` com recorte de warm-up, integração temporal de `E[N]` e
  utilização individual dos servidores;
- `RunMetrics`, `ServerUtilization` e eventos imutáveis;
- invariantes de topologia, capacidade, eventos e conservação;
- logs estruturados de configuração, eventos e resumo;
- `LoadBalancer`;
- políticas Aleatória, Round Robin e Fila Mais Curta em módulo próprio, com
  sementes reproduzíveis e desempates aleatórios;
- gerador de chegadas Poisson reproduzível;
- geração antecipada de traços imutáveis com chegada e duração de serviço;
- executor de uma rodada completa com sementes independentes, invariantes,
  métricas e logs;
- testes unitários e teste de integração do ciclo completo de uma requisição;
- notebooks de configuração e integração.

Em 8 de setembro de 2026, a suíte possui **206 testes aprovados**.

## Alinhamentos ainda necessários

Ainda faltam:

- executor das 150 rodadas estáveis;
- modelo analítico `M/M/1`;
- experimento instável com `lambda=3,3`;
- intervalos de confiança, CSVs, gráficos e CLI.

O gerador Poisson já está alinhado ao novo enunciado. Pareto Limitada, Hurst e
rajadas de 30 a 120 não fazem mais parte dos requisitos vigentes.

## Componentes

| Componente | Responsabilidade |
| --- | --- |
| `SimulationConfig` | Configura capacidade 1, `mu=1`, horizonte 5000 e warm-up 500. |
| `Request` | Mantém IDs, chegada, atribuição, início, conclusão e tempos derivados. |
| `Server` | Sorteia serviços exponenciais, mantém fila FIFO e publica callbacks de início e conclusão. |
| `ServerState` | Fotografia imutável do estado de um servidor. |
| `LoadBalancer` | Valida servidores e requisições, seleciona um servidor e inicia o atendimento. |
| `RandomPolicy` | Escolhe um servidor pseudoaleatoriamente. |
| `RoundRobinPolicy` | Distribui requisições ciclicamente. |
| `ShortestQueuePolicy` | Escolhe a menor ocupação e desempata pseudoaleatoriamente. |
| `PoissonTrafficGenerator` | Produz chegadas Poisson no ambiente SimPy. |
| `RequestTraceEntry` | Preserva chegada e duração de serviço de uma requisição. |
| `MetricsCollector` | Preserva eventos e calcula métricas na janela `[warmup, horizon)`. |
| `RunMetrics` | Resume vazão, tempos, `E[N]` e utilizações de uma rodada. |
| `ServerUtilization` | Associa a utilização temporal ao identificador do servidor. |
| `SimulationLogger` | Emite configuração, eventos e resumo. |
| `run_simulation` | Monta, executa e valida uma rodada completa. |
| `SimulationResult` | Reúne configuração, sementes, traço, métricas e eventos. |
| `validate_simulation_invariants` | Valida topologia, ciclos de vida e conservação. |

## Preparação do ambiente

### Linux

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Após o ambiente ter sido configurado, você poderá executar o notebook "experimentos_balanceador_carga.ipynb" que demonstra todos os resultados obtidos dentro do relatório. Além disso, você deve utilizar o .venv como kernel do Jupyter Notebook.

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

## Tempo de serviço

Por padrão, cada servidor sorteia uma duração exponencial de média
`1/service_rate`. A semente torna a sequência reproduzível:

```python
server = Server(environment, server_id=0, service_rate=1.0, seed=123)
```

Testes e futuros traços de carga podem fornecer um sampler próprio:

```python
server = Server(
    environment,
    server_id=0,
    service_time_sampler=lambda request: 0.05,
)
```

Essa injeção permite usar durações conhecidas nos testes e, futuramente,
reutilizar a mesma demanda de serviço nas três políticas.

## Métricas temporais

O cálculo recebe explicitamente a janela e todos os servidores, inclusive os
que permaneceram ociosos:

```python
metrics = collector.calculate_run_metrics(
    horizon=config.horizon,
    warmup=config.warmup,
    servers=servers,
)
```

Eventos anteriores ao warm-up atualizam o estado inicial da integração, mas
não acumulam área. Eventos exatamente no warm-up são incluídos; eventos no
horizonte são excluídos.

## Execução de uma rodada

Uma rodada completa pode ser executada diretamente a partir da configuração:

```python
from load_balancer_sim import SimulationConfig, run_simulation

result = run_simulation(SimulationConfig())
print(result.metrics)
```

`result.trace` pode ser fornecido novamente a `run_simulation` com outra
política. Isso conserva os mesmos instantes de chegada e demandas de serviço.

## Estrutura atual

```text
src/load_balancer_sim/
├── __init__.py
├── config.py
├── invariants.py
├── load_balancer.py
├── logs.py
├── metrics.py
├── policies.py
├── request.py
├── server.py
├── simulation.py
└── traffic.py

tests/
├── test_config.py
├── test_environment.py
├── test_invariants.py
├── test_load_balancer.py
├── test_logs.py
├── test_metrics.py
├── test_policies.py
├── test_request.py
├── test_server.py
├── test_simulation.py
└── test_traffic.py
```

Os notebooks em `notebooks/` são materiais auxiliares. O fluxo definitivo da
simulação deve residir nos módulos do pacote, sem acessar atributos privados.

## Próximo commit técnico

O próximo marco é executar as 150 rodadas estáveis, reutilizar o mesmo traço
entre políticas, agregar resultados e calcular intervalos de confiança de 95%.
