# LangGraph Agent

Um agente inteligente construído com LangGraph e Anthropic Claude, capaz de escolher entre agentes ReAct e CodeAct para resolver tarefas de forma adaptativa.

## Características

- **Agente duplo:** Dependendo da complexidade da tarefa, o sistema seleciona automaticamente entre:
  - **ReAct Agent:** Para tarefas simples envolvendo uma única ferramenta
  - **CodeAct Agent:** Para tarefas complexas que envolvem múltiplas ferramentas ou lógica avançada

- **Integração com Ferramentas MCP:**
  - Serviço de meteorologia
  - Operações matemáticas
  - Consultas SQLite

- **Processamento em Português:** O agente é capaz de compreender e responder a perguntas em Português de Portugal.

## Requisitos

- Python 3.9+
- Anthropic API Key (para Claude)
- OpenWeather API Key (para o serviço de meteorologia)

## Configuração

1. Clone o repositório:
```bash
git clone https://github.com/seu-username/langgraph-agent.git
cd langgraph-agent
```

2. Instale as dependências necessárias:
```bash
pip install langchain-core langgraph langchain-anthropic python-dotenv
```

3. Crie um ficheiro `.env` na raiz do projeto com as suas chaves API:
```
ANTHROPIC_API_KEY=sua_chave_api_da_anthropic
OPENWEATHER_API_KEY=sua_chave_api_do_openweather
```

## Estrutura do Projeto

- `implementation.py`: Implementação principal do agente
- `stub.py`: Stub do CustomAgent para integração com LangGraph
- `spec.yml`: Especificação do agente
- `mcp-servers/`: Servidores MCP para ferramentas específicas
- `data/`: Base de dados e outros recursos

## Uso

Execute o agente com:

```bash
python implementation.py
```

O sistema executará automaticamente exemplos de teste com diferentes cenários.

## Exemplos de Consultas

- "Qual é o tempo em Lisboa?"
- "Qual é o tempo no Porto e calcula a soma de 10 e 5?"
- "Lista as tabelas da base de dados de viagens"

## Licença

[MIT](LICENSE)

## Contribuições

Contribuições são bem-vindas! Por favor, sinta-se à vontade para submeter um Pull Request. 