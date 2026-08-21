TESTS:

- GET http://127.0.0.1:5000/begin          >> works
- GET http://127.0.0.1:5000/game           >> works
- GET http://127.0.0.1:5000/game/game_id   >> works
- POST http://127.0.0.1:5000/guess         >> works

```bash
curl -X POST http://127.0.0.1:5000/guess -H "Content-Type: application/json" -d '{"gameID": "1", "guess": "1111"}'
```
```bash 
{
  "gameId": "1",
  "guessTime": "2026-08-21T11:27:58.382078",
  "result": "e:1:p:1"
}
```

- GET http://127.0.0.1:5000/rounds/game_id >> works