# Relatório

**Nome:** Guilherme Webster Chamoun  
**RA:** 257111

## Introdução

O objetivo deste trabalho é criar um servidor web que recebe (e atende) requisições de maneira concorrente. Devemos usar socket TCP e o único método que precisamos implementar é o `GET`.

## Descrição geral

O código do projeto foi desenvolvido de acordo com o seguinte passo a passo:

- Iniciar servidor e esperar conexão
- Estabelecer conexão
- Enviar arquivo ou erro
- Um cliente pode fazer várias requisições consecutivas

A abordagem arquitetural final é tal que a *thread* principal cria o socket do servidor; então, bindamos via método `bind()` a porta `8080`. Com o método `listen()` habilitamos espera por conexões. Então, `accept()` produz um socket para cada cliente. Uma nova *thread* recebe este socket. Esta recebe e processa uma requisição, envia resposta e então encerra a conexão. 

## Casos de uso

Temos 3 casos possíveis:

1. **Arquivo existente (`index.html`):** o servidor está ouvindo e pronto para estabelecer conexões; o cliente solicita o arquivo indicado via rota correta. O servidor retorna o arquivo solicitado.
2. **Arquivo inexistente:** o servidor está ouvindo e pronto para estabelecer conexões; o cliente solicita um arquivo que não existe no diretório local. O servidor retorna mensagem de erro informando que o arquivo solicitado não existe.
3. **Clientes simultâneos:** o servidor está esperando, pronto para receber conexões. Vários clientes fazem diferentes solicitações; cada cliente é atendido por uma *thread*, enquanto a *thread* principal fica responsável por criar outras *threads* para atender novos clientes. Ademais, as *threads* que atendem conexões de cada cliente encerram a conexão no final do atendimento. A *thread* principal, por sua vez, encerra o servidor quando há interrupção do teclado. 

## Estruturas de dados

- `serverSocket`: socket TCP principal;
- `connectionSocket`: socket exclusivo de uma conexão;
- `addr`: tupla contendo IP e porta do cliente;
- `messageBytes`: requisição recebida como bytes;
- `message`: requisição convertida para texto;
- `method`, `filename` e `version`: partes extraídas da linha HTTP;
- `responseHeader`, `body` e `response`: componentes da resposta HTTP;
- `clientThread`: objeto que representa a *thread* de atendimento.
 
## Detalhes de implementação

- uso de `AF_INET` serve para lidar com endereços IPv4;
- uso de `SOCK_STREAM` significa que estamos criando um socket TCP;
- `SO_REUSEADDR` é usado para evitar muitos erros de endereço já em uso;
- todas as interfaces da máquina *host* ficam disponíveis com `bind(("", 8080))`;
- `serverSocket` traz a interface do servidor, a qual abarca os `connectionSocket` que lidam com conexões em particular;
- conversão entre bytes e texto é realizada na recepção e envio de pacotes com `decode()` e `encode()`;
- fechamento do socket (tanto do servidor quanto da conexão) ocorre via `finally`, depois de um `try` que tenta abrir o arquivo solicitado;

## Testes e validação

Para testar se de fato o processamento foi concorrente, usamos uma máquina de um laboratório do IC como *host* e outra máquina (do mesmo laboratório) como cliente, executando um script Bash para realizar várias requisições. De fato, os clientes eram atendidos rapidamente.

Anteriormente, o código foi implementado de maneira sequencial para primeiro ter um servidor que funcionasse, ou seja, criasse um servidor, o qual ouvia requisições, processava, e enviava pacotes. A versão sequencial funcional era de fato mais lenta que a concorrente atual.

## Conclusão

- O objetivo de criar um servidor concorrente foi realizado com sucesso.
- De fato, este foi implementado com sockets TCP, atendendo requisições HTTP.
- Uma abordagem inicial mais simples foi transformada em uma abordagem concorrente via `threading`.
- A abordagem concorrente de fato é mais rápida que a sequencial trivial.
- Uma possível melhoria seria validar o método que o servidor recebeu do usuário de maneira a determinar se de fato foi um `GET` com sintaxe válida.
