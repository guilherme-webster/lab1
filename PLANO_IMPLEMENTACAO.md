# Plano de implementação - Trabalho 1 de MC714

Este documento transforma o enunciado de `MC714_2s2026.pdf` em um roteiro de implementação. A solução proposta usa **Python + SimPy**, porque o trabalho é uma simulação de eventos discretos e o SimPy já oferece relógio simulado, processos, filas e recursos com capacidade limitada.

> Prazo informado no enunciado: **22 de setembro de 2026**. O trabalho deve ser feito em dupla e entregue como um relatório IEEE de no máximo 4 páginas e um arquivo compactado com o código.

## 1. O que precisa ser entregue

A implementação obrigatória deve conter:

- 3 servidores homogêneos;
- capacidade de 15 requisições simultâneas por servidor;
- tempo de serviço constante de 0,05 unidade de tempo;
- filas monitoradas durante toda a execução;
- políticas Aleatória, Round Robin e Fila Mais Curta;
- tráfego com Pareto Limitada e parâmetro de Hurst `H = 0,8`;
- experimentos independentes para rajadas máximas de 30, 60, 90 e 120 requisições;
- horizonte máximo de 200 unidades de tempo;
- 10 repetições independentes de cada configuração;
- throughput e tempo médio de resposta;
- modelo analítico com probabilidade `1/3` de encaminhamento a cada servidor;
- comparação quantitativa entre modelo e simulação;
- logs da dinâmica do balanceamento;
- instruções para execução em Windows e Linux.

Com 3 políticas, 4 limites de rajada e 10 repetições, o conjunto mínimo possui:

```text
3 x 4 x 10 = 120 execuções
```

## 2. Decisões que eu confirmaria com o professor

O enunciado não define completamente o processo de chegada. Antes de congelar a implementação, eu perguntaria:

1. A Pareto Limitada deve modelar o **intervalo entre chegadas**, o **tamanho das rajadas** ou períodos ON/OFF?
2. Quais são os limites inferior e superior da distribuição, além dos máximos 30, 60, 90 e 120?
3. Cada rajada deve ter exatamente 30, 60, 90 ou 120 requisições, ou esses números são limites máximos? A expressão “rajadas de no máximo 30” sugere que são máximos.
4. Ao atingir `t = 200`, requisições que ainda estão no sistema devem ser descartadas da medição ou a geração deve parar e o sistema pode terminar de drená-las?
5. O modelo analítico esperado é uma fila `M/M/15` por servidor, mesmo que a simulação tenha serviço determinístico e chegadas em rajadas?

Sem uma resposta, eu adotaria e documentaria estas hipóteses:

- o limite de rajada `B` é o máximo, não um tamanho fixo;
- o tamanho de cada rajada é uma Pareto Limitada discretizada no intervalo `[1, B]`;
- uso a relação usual de um modelo ON/OFF de cauda pesada, `H = (3 - alpha)/2`, resultando em `alpha = 3 - 2H = 1,4`;
- todas as requisições de uma rajada chegam no mesmo instante, e os intervalos entre rajadas são configuráveis e também limitados;
- a geração termina em `t = 200`; o throughput oficial conta conclusões até esse instante;
- também registro o backlog em `t = 200`, para deixar explícitas as requisições censuradas;
- o modelo `M/M/15` é tratado como uma aproximação analítica de referência, e não como descrição exata do tráfego Pareto com serviço determinístico.

Essas escolhas precisam aparecer no relatório. A relação entre `H` e `alpha` depende do modelo de tráfego; portanto, não se deve apenas escrever `alpha = 1,4` sem explicar a hipótese ON/OFF adotada.

## 3. Tecnologias e organização sugeridas

### Dependências

- Python 3.11 ou mais recente;
- SimPy para a simulação de eventos discretos;
- NumPy ou SciPy para os números aleatórios e a Pareto truncada;
- pandas para consolidar as 10 repetições;
- Matplotlib para os gráficos;
- pytest para testes automatizados.

### Estrutura do repositório

```text
lab1/
├── README.MD
├── pyproject.toml                # dependências e configuração do projeto
├── src/
│   └── load_balancer_sim/
│       ├── __init__.py
│       ├── config.py             # parâmetros e validação
│       ├── request.py            # dados e timestamps da requisição
│       ├── server.py             # servidor, recurso e fila
│       ├── policies.py           # Random, Round Robin e Shortest Queue
│       ├── traffic.py            # Pareto Limitada e traços de chegada
│       ├── metrics.py            # eventos, métricas e agregação
│       ├── analytical.py         # modelo M/M/15 e fórmulas
│       ├── simulation.py         # montagem e execução de uma rodada
│       ├── experiments.py        # matriz de 120 execuções
│       ├── plots.py              # gráficos e tabelas
│       └── cli.py                # interface de linha de comando
├── tests/
│   ├── test_traffic.py
│   ├── test_policies.py
│   ├── test_server.py
│   ├── test_metrics.py
│   ├── test_analytical.py
│   └── test_integration.py
├── configs/
│   └── default.toml
├── results/                      # CSVs e figuras gerados, não código manual
└── report/                       # fonte LaTeX IEEE e referências
```

## 4. Arquitetura da simulação

O fluxo de uma requisição seria:

```text
Gerador de tráfego
        |
        v
Balanceador -- escolhe uma política configurada
        |
        +----------+----------+
        v          v          v
   Servidor 0  Servidor 1  Servidor 2
   15 slots    15 slots    15 slots
   fila FIFO   fila FIFO   fila FIFO
        \          |          /
         +---- coletor de métricas ----> CSV + gráficos
```

### Entidades principais

`Request`

- `id`;
- `burst_id`;
- `arrival_time`;
- `assigned_server`;
- `service_start_time`;
- `completion_time`;
- `queue_time = service_start_time - arrival_time`;
- `response_time = completion_time - arrival_time`.

`Server`

- contém um `simpy.Resource(capacity=15)`;
- mantém `active_count`, tamanho da fila e máximo observado;
- solicita um slot, espera, processa por `0.05` e libera o slot;
- nunca usa tempo real (`sleep`); usa somente `yield env.timeout(0.05)`.

`LoadBalancer`

- recebe a lista dos três servidores e uma política;
- chama `policy.select(servers)` a cada chegada;
- registra a decisão `(tempo, request_id, servidor, ativos, filas)`;
- não conhece detalhes internos do gerador de tráfego.

`MetricsCollector`

- recebe eventos de chegada, roteamento, início e fim de serviço;
- guarda dados detalhados por requisição;
- amostra ou registra por evento o estado de cada servidor;
- calcula métricas somente a partir dos eventos, evitando contadores duplicados.

Separar esses componentes permite testar as políticas sem executar a simulação completa.

## 5. Passo a passo de implementação

### Passo 1 - Criar configuração e execução mínima

Criar uma configuração imutável com, pelo menos:

```python
SimulationConfig(
    policy="round_robin",
    server_count=3,
    server_capacity=15,
    service_time=0.05,
    burst_max=30,
    hurst=0.8,
    horizon=200.0,
    seed=12345,
)
```

Validar valores na entrada: política conhecida, `burst_max` pertencente a `{30, 60, 90, 120}`, capacidades positivas e `0 < H < 1`.

**Pronto quando:** um comando carrega a configuração, cria um ambiente SimPy e encerra em `t = 200` sem tráfego.

### Passo 2 - Implementar e testar uma requisição em um servidor

Implementar `Server.handle(request)` como processo SimPy:

1. registrar a chegada à fila;
2. solicitar o `Resource`;
3. ao obter o slot, registrar início do serviço;
4. executar `yield env.timeout(0.05)`;
5. registrar conclusão e liberar o recurso.

O `with resource.request() as slot:` é conveniente porque garante a liberação do recurso.

**Pronto quando:** um teste envia 16 requisições no mesmo instante, confirma que apenas 15 começam imediatamente e que a 16ª começa em `t = 0.05`.

### Passo 3 - Implementar as três políticas

Definir uma interface comum, por exemplo `select(servers, rng) -> Server`.

1. **Aleatória:** selecionar uniformemente um índice entre 0 e 2 usando um gerador pseudoaleatório recebido por parâmetro.
2. **Round Robin:** manter um contador privado e produzir `0, 1, 2, 0, 1, 2, ...`.
3. **Fila Mais Curta:** minimizar uma tupla como `(waiting_count, active_count, server_id)`. Isso prioriza a menor fila de espera, depois o menor número em serviço e, por fim, resolve empates de forma determinística.

O critério de desempate deve ser descrito no relatório. Outra opção válida é desempatar aleatoriamente, desde que seja reproduzível pela semente.

**Pronto quando:** testes unitários comprovam a sequência Round Robin, a reprodutibilidade da política Aleatória e todas as situações de empate da Fila Mais Curta.

### Passo 4 - Implementar a Pareto Limitada

Para limites `x_min` e `x_max`, expoente `alpha > 0` e `x_min <= x <= x_max`, a função de distribuição acumulada é:

```text
F(x) = [1 - (x_min/x)^alpha] / [1 - (x_min/x_max)^alpha]
```

Pelo método da transformada inversa, com `u` uniforme em `[0,1)`:

```text
x = x_min / [1 - u(1 - (x_min/x_max)^alpha)]^(1/alpha)
```

Para uma rajada, eu usaria `x_min = 1`, `x_max = B`, converteria o resultado para inteiro e garantiria `1 <= tamanho <= B`. A regra de arredondamento deve ser única e testada.

A média teórica da Pareto Limitada, útil para validar o gerador, é:

```text
E[X] = alpha*x_min^alpha / [1 - (x_min/x_max)^alpha]
       * [x_max^(1-alpha) - x_min^(1-alpha)] / (1-alpha), alpha != 1
```

É possível usar `scipy.stats.truncpareto`, mas eu ainda escreveria um teste da fórmula e dos limites para evitar parametrizar `scale` e o limite normalizado incorretamente.

**Pronto quando:** um teste com muitas amostras confirma os limites, a reprodutibilidade e uma média empírica próxima da média teórica.

### Passo 5 - Gerar um traço de chegadas reutilizável

Antes de comparar políticas, gerar uma lista imutável:

```text
ArrivalTrace = [(arrival_time, request_id, burst_id), ...]
```

Para cada par `(burst_max, repetição)`, gerar o traço apenas uma vez. Reutilizar exatamente esse traço nas três políticas. Isso evita que uma política pareça melhor apenas por ter recebido tráfego mais leve ao acaso.

Sugestão para sementes:

```text
traffic_seed = base_seed + 1000 * burst_max + repetition
routing_seed = traffic_seed + policy_specific_offset
```

A semente de tráfego não deve depender da política. A Aleatória pode ter uma segunda fonte de aleatoriedade apenas para o roteamento.

**Pronto quando:** as três políticas recebem os mesmos tempos e IDs de chegada para a mesma repetição, e repetições distintas recebem traços independentes.

### Passo 6 - Definir claramente a janela de medição

Eu adotaria o seguinte protocolo:

- gerar chegadas apenas com `arrival_time < 200`;
- executar a medição oficial até `t = 200`;
- contar como concluídas na janela apenas as requisições com `completion_time <= 200`;
- registrar, em `t = 200`, quantas estão em serviço e quantas aguardam;
- opcionalmente executar uma fase de drenagem separada, sem misturá-la com o throughput oficial.

Essa decisão evita ultrapassar silenciosamente a duração máxima. Se o professor autorizar drenagem depois de `t = 200`, usar o tempo de resposta de todas as requisições que chegaram na janela e identificar essa regra no relatório.

### Passo 7 - Implementar logs e invariantes

Oferecer dois níveis de saída:

- `INFO`: configuração e resumo de cada rodada;
- `DEBUG`: uma linha por evento, adequada ao requisito de “logs detalhados”.

Formato útil:

```text
time,event,request_id,burst_id,server_id,active,queue_length
```

Verificar durante ou ao fim de cada rodada:

```text
0 <= active_count <= 15
arrivals = completed + waiting_at_end + active_at_end
service_start >= arrival_time
completion_time >= service_start_time
```

### Passo 8 - Calcular as métricas por rodada

Para uma janela de tamanho `T = 200`:

```text
throughput = número de requisições concluídas até T / T
response_time_i = completion_time_i - arrival_time_i
average_response_time = média dos response_time_i concluídos na janela
```

Também registraria, mesmo não sendo obrigatório:

- número de chegadas e conclusões;
- requisições pendentes em `t = 200`;
- tempo médio de espera;
- utilização média por servidor;
- comprimento médio e máximo das filas;
- percentil 95 do tempo de resposta;
- distribuição de requisições entre servidores.

O CSV por rodada deve possuir uma linha com `policy`, `burst_max`, `repetition`, `seed` e todas as métricas. Manter outro CSV por requisição ajuda a auditar resultados, mas pode ser ativado apenas com uma opção para não gerar arquivos enormes.

### Passo 9 - Executar e agregar os 120 experimentos

Laços conceituais:

```python
for burst_max in (30, 60, 90, 120):
    for repetition in range(10):
        trace = generate_trace(burst_max, repetition)
        for policy in ("random", "round_robin", "shortest_queue"):
            result = run_once(trace, policy)
            save(result)
```

Calcular a média das 10 repetições para cada par `(policy, burst_max)`. Além da média exigida, calcular desvio-padrão e intervalo de confiança de 95%:

```text
IC95 = média +/- t_(0.975, 9) * desvio_amostral / sqrt(10)
```

Com apenas 10 amostras, usar a distribuição t de Student é mais apropriado que usar diretamente `1,96`.

**Pronto quando:** há 120 linhas de resultados individuais e 12 linhas agregadas.

### Passo 10 - Implementar o modelo analítico

Como aproximação inicial, modelar cada servidor como uma fila `M/M/15` homogênea. O balanceamento justo produz:

```text
lambda_s = lambda_total / 3
mu = 1 / 0.05 = 20 requisições por unidade de tempo, por slot
c = 15 slots por servidor
capacidade por servidor = c*mu = 300
capacidade total = 3*c*mu = 900 requisições por unidade de tempo
rho = lambda_s / (c*mu) = lambda_total / 900
```

Usar como `lambda_total` a taxa média efetiva do traço de chegada, isto é, `arrivals / 200`, e informar esse valor em cada cenário. O regime estacionário só existe para `rho < 1`.

Definindo `a = lambda_s/mu`, para `rho < 1`:

```text
P0 = 1 / [sum(n=0..c-1, a^n/n!) + a^c/(c!*(1-rho))]

P_wait = [a^c/(c!*(1-rho))] * P0

Wq = P_wait / (c*mu - lambda_s)

W = Wq + 1/mu
```

Assim, `W` é o tempo médio de resposta teórico. Em regime estável, o throughput teórico total é aproximadamente `lambda_total`; se `lambda_total >= 900`, o modelo estacionário não é válido e a fila cresce sem limite.

Para evitar overflow em fatoriais e potências, calcular os termos recursivamente ou no domínio logarítmico.

#### Limitação que precisa ser discutida

`M/M/15` supõe chegadas de Poisson e serviço exponencial. A simulação pedida tem chegadas Pareto em rajadas e serviço determinístico. Portanto, diferenças não são necessariamente erros: elas medem também o efeito de burstiness e da diferença entre os modelos.

Se houver tempo, eu acrescentaria uma aproximação `M/D/15` ou uma aproximação `G/G/c` como análise complementar, mas manteria o `M/M/15` simples e completamente deduzido como baseline. Para a política Fila Mais Curta, a escolha é dependente do estado; por simetria, a fração marginal pode tender a `1/3`, mas seu tempo de resposta pode ser melhor que o previsto pelo modelo de divisão independente.

### Passo 11 - Comparar simulação e teoria

Para cada cenário, produzir uma tabela como:

```text
policy | burst_max | lambda | rho | throughput_sim | throughput_teo |
erro_%_throughput | response_sim | response_teo | erro_%_response
```

Erro relativo:

```text
erro_relativo_% = 100 * abs(simulado - teórico) / abs(teórico)
```

Se o valor teórico for zero ou o sistema estiver instável, não calcular o percentual; marcar como não aplicável e explicar.

Gráficos mais úteis para o relatório:

1. throughput médio versus limite da rajada, uma curva por política;
2. tempo médio de resposta versus limite da rajada, uma curva por política;
3. simulado versus analítico, com barras de erro de 95%;
4. um gráfico curto da fila ao longo do tempo para ilustrar a dinâmica, se houver espaço.

Não colocar todos os logs no relatório. Usar logs para validação e apresentar apenas gráficos e tabelas que respondam à comparação.

### Passo 12 - Preparar CLI, documentação e empacotamento

Comandos desejáveis:

```bash
python -m load_balancer_sim.cli run --policy round_robin --burst-max 60 --seed 123
python -m load_balancer_sim.cli all --repetitions 10 --output results
python -m load_balancer_sim.plots --input results/summary.csv
pytest
```

O `README.MD` final deve explicar criação do ambiente, instalação, execução de uma rodada, execução completa e localização dos resultados. Preferir `pathlib` e evitar comandos ou caminhos exclusivos de um sistema operacional, para manter compatibilidade com Windows e Linux.

## 6. Plano de testes

### Testes unitários

- amostras Pareto sempre dentro dos limites;
- média empírica coerente com a expressão teórica;
- mesma semente gera o mesmo traço;
- Round Robin produz sequência cíclica exata;
- Aleatória só retorna servidores válidos e é reproduzível;
- Fila Mais Curta seleciona corretamente e resolve empates como documentado;
- servidor nunca excede 15 requisições ativas;
- tempo de serviço é exatamente 0,05;
- fórmulas de Erlang C batem com casos calculados à mão.

### Testes de integração e sanidade

- com uma única requisição e servidor livre, o tempo de resposta é 0,05;
- com 16 requisições simultâneas em um servidor, 15 terminam em 0,05 e uma em 0,10;
- sob carga baixa, throughput fica próximo da taxa de chegada e resposta próximo de 0,05;
- sob sobrecarga, o backlog e as filas crescem;
- `arrivals = completed + active + queued` no fim da janela;
- as três políticas recebem o mesmo traço em comparações pareadas;
- repetir o comando com as mesmas sementes produz arquivos idênticos, exceto por metadados dispensáveis.

## 7. Estrutura sugerida para o relatório de 4 páginas

Como o limite é curto, eu distribuiria o espaço assim:

1. **Resumo:** problema, três políticas, método e principal resultado.
2. **Arquitetura e metodologia:** diagrama pequeno, servidores, capacidade, serviço, tráfego, parâmetros, sementes e 10 repetições.
3. **Modelo analítico:** divisão `1/3`, `lambda_s`, `mu`, `rho`, Erlang C, hipóteses e limitações.
4. **Resultados e discussão:** dois gráficos principais, uma tabela compacta, IC de 95% e explicação das diferenças.
5. **Conclusão:** qual política se saiu melhor, efeito das rajadas e limitações.
6. **Divisão do trabalho:** uma frase ou tabela curta, compatível com os commits.

Começar o relatório cedo, já no template IEEE de duas colunas. Os resultados devem ser gerados automaticamente pelo código, para evitar copiar números incorretos manualmente.

## 8. Ordem prática de trabalho da dupla

Uma divisão equilibrada, mantendo revisão cruzada, seria:

- integrante A: servidor, métricas, logs e testes de capacidade;
- integrante B: tráfego Pareto, políticas e testes de distribuição;
- ambos: protocolo experimental, modelo analítico, gráficos e relatório;
- cada integrante revisa o código produzido pelo outro.

Fazer commits pequenos e descritivos. A divisão declarada no relatório deve refletir o histórico real do repositório.

## 9. Cronograma sugerido

- **Semana 1:** esclarecer ambiguidades, montar estrutura, servidor e requisição.
- **Semana 2:** três políticas e testes unitários.
- **Semana 3:** gerador Pareto, traços reproduzíveis e logs.
- **Semana 4:** executor das 120 rodadas, métricas e CSVs.
- **Semana 5:** modelo analítico, validação e gráficos.
- **Semana 6:** relatório IEEE, execução em Windows/Linux e revisão final.

Reservar alguns dias para repetir todos os experimentos depois da última alteração. Não misturar resultados de versões diferentes do simulador.

## 10. Materiais para estudo

### Simulação com SimPy

- [Visão geral do SimPy](https://simpy.readthedocs.io/en/stable/index.html): introdução à simulação de eventos discretos.
- [Conceitos básicos do SimPy](https://simpy.readthedocs.io/en/stable/topical_guides/simpy_basics.html): ambiente, eventos e processos geradores.
- [Recursos compartilhados](https://simpy.readthedocs.io/en/stable/topical_guides/resources.html): base para representar os 15 slots de cada servidor.
- [Monitoramento no SimPy](https://simpy.readthedocs.io/en/stable/topical_guides/monitoring.html): exemplos de coleta de uso e tamanho de fila.

### Pareto, dados e gráficos

- [Pareto truncada no SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.truncpareto.html): definição, suporte, parâmetros e geração de amostras.
- [GroupBy no pandas](https://pandas.pydata.org/pandas-docs/stable/user_guide/groupby.html): agregação das 10 repetições.
- [Introdução ao Matplotlib](https://matplotlib.org/stable/users/getting_started/index.html): geração dos gráficos do relatório.

### Qualidade e relatório

- [Documentação do pytest](https://docs.pytest.org/en/stable/): testes unitários, fixtures e parametrização.
- [Templates oficiais de conferência IEEE](https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/authoring-tools-and-templates/): modelo de duas colunas em LaTeX ou Word.

Ao estudar filas, procurar especificamente pelos termos **Erlang C**, **fila M/M/c**, **utilização rho**, **Little's Law** e **simulação de eventos discretos**. Para tráfego auto-similar, estudar **modelos ON/OFF de cauda pesada**, deixando claro que a conversão entre Hurst e o expoente de Pareto depende das hipóteses do modelo.

## 11. Checklist final

- [ ] As ambiguidades do tráfego foram confirmadas ou documentadas como hipóteses.
- [ ] Existem exatamente 3 servidores homogêneos com capacidade 15.
- [ ] O tempo de serviço é fixo em 0,05.
- [ ] As três políticas são selecionáveis por configuração.
- [ ] Os quatro limites de rajada foram executados separadamente.
- [ ] Cada configuração tem 10 sementes independentes.
- [ ] As políticas usam o mesmo traço de chegada em cada comparação.
- [ ] Nenhuma chegada ocorre depois de `t = 200`.
- [ ] Throughput e tempo médio de resposta possuem definição explícita.
- [ ] Filas, ativos e backlog são monitorados.
- [ ] O modelo analítico usa transição `1/3` e documenta suas hipóteses.
- [ ] Há comparação numérica, erro relativo e gráficos com barras de erro.
- [ ] Testes automatizados passam.
- [ ] O projeto executa em Windows e Linux.
- [ ] O relatório está em formato IEEE e possui no máximo 4 páginas.
- [ ] A divisão do trabalho é compatível com os commits.
- [ ] Os arquivos finais seguem os nomes exigidos no enunciado.

