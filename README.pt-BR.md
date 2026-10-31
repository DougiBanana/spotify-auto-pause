# spotify-auto-pause

Pausa o Spotify automaticamente quando outro app começa a tocar áudio e volta a tocar quando esse áudio para. Funciona como o "foco de áudio" do celular, mas no desktop Linux.

English: see [README.md](README.md).

## Como funciona

Um serviço pequeno em segundo plano (serviço de usuário do systemd) observa os streams de áudio do sistema. Quando um app da sua lista de gatilhos (navegador, VLC, mpv, uma chamada...) começa a tocar som, o Spotify é pausado. Quando esse som para, o Spotify volta.

- Só o Spotify é controlado. O app que disparou a pausa nunca é mexido.
- O áudio do próprio Spotify nunca conta como gatilho.
- Apps fora da lista de gatilhos (jogos, por exemplo) nunca pausam o Spotify.
- O Spotify só volta se foi o script que pausou, então ele não liga uma música que você mesmo parou.
- Um pequeno atraso (0,5 s por padrão) filtra sons de notificação e streams que abrem e fecham rápido.

## Requisitos

| Precisa de | Pacote (Arch) | Pacote (Debian/Ubuntu, Fedora, openSUSE) |
|---|---|---|
| Python 3 | `python` | `python3` |
| `playerctl` | `playerctl` | `playerctl` |
| `pactl` com saída JSON (PulseAudio 15+ ou PipeWire com `pipewire-pulse`) | `libpulse` | `pulseaudio-utils` |
| Sessão de usuário do systemd | já incluído | já incluído |

O instalador confere tudo isso e oferece instalar o que faltar (suporta pacman, apt, dnf e zypper).

## Instalação

```bash
git clone https://github.com/DougiBanana/spotify-auto-pause.git
cd spotify-auto-pause
./install.sh
```

Se o `./install.sh` der "permissão negada", use `bash install.sh`.

O instalador:
- copia o script para `~/.local/share/spotify-auto-pause/`
- cria `~/.config/spotify-auto-pause/config.json` (uma config existente nunca é sobrescrita)
- cria o comando `~/.local/bin/spotify-auto-pause` para diagnóstico
- cria, ativa e inicia o serviço de usuário, então ele roda a cada login

## Configuração

Edite `~/.config/spotify-auto-pause/config.json` e depois rode `systemctl --user restart spotify-auto-pause`.

| Chave | Padrão | Significado |
|---|---|---|
| `player` | `"spotify"` | Player MPRIS controlado (o nome que o `playerctl -l` mostra). |
| `trigger_apps` | navegadores, `vlc`, `mpv`, `webrtc` | Textos procurados no nome do app, no executável ou no título do stream (sem diferenciar maiúsculas). Se bater, aquele app pausa o Spotify. |
| `ignore_apps` | `[]` | Streams que baterem com algum desses textos nunca disparam a pausa. É checado antes de `trigger_apps`. |
| `debounce_seconds` | `0.5` | O áudio precisa durar esse tempo antes de o Spotify pausar. |
| `verbose` | `false` | Registra todos os eventos de áudio no log (útil para depurar). |

A comparação é por trecho do texto: `"chrom"` pega Chrome e Chromium, `"firefox"` pega `firefox`, `firefox-esr` e `firefox-developer-edition`, e `"webrtc"` pega chamadas de navegador e do Discord.

### Descobrindo os nomes certos

Toque algo no app que você quer usar como gatilho e rode:

```bash
spotify-auto-pause --list
```

Ele mostra todos os streams de áudio ativos agora e como cada um é tratado:

```
APP NAME               BINARY             STREAM TITLE             CORKED  RESULT
spotify                spotify                                     False   player itself
firefox                firefox            audioipc server          False   TRIGGER
```

Para transformar um app em gatilho, adicione um pedaço do nome ou do executável dele em `trigger_apps`.

## Solução de problemas

- **Ver se está rodando:** `systemctl --user status spotify-auto-pause`
- **Ler o log:** `journalctl --user -u spotify-auto-pause -f`. Cada pausa é registrada com o stream que a causou.
- **Nada acontece com um vídeo:** o vídeo precisa estar tocando som. Vídeos mudos (como os que começam sozinhos nas redes sociais) não criam stream de áudio. Use o `--list` com o vídeo tocando com som.
- **O Spotify pausa quando não devia:** rode `--list` ou leia o log para ver qual stream disparou, e adicione um pedaço do nome dele em `ignore_apps`.
- **Um jogo não devia pausar o Spotify mas pausa:** alguma entrada de `trigger_apps` está casando com ele. Deixe essa entrada mais específica ou coloque o jogo em `ignore_apps`.
- **Spotify via Flatpak:** ele também usa o nome MPRIS `spotify`, então a config padrão deve funcionar. Confira com `playerctl -l`.

## Desinstalação

```bash
./uninstall.sh          # mantém sua config
./uninstall.sh --purge  # apaga a config também
```

## Limitações

- Ele reage a streams de áudio, não a janelas. Qualquer coisa que toque som pelo PipeWire ou PulseAudio pode disparar a pausa se bater com `trigger_apps`.
- Só um player é controlado (`player`).
- Funciona em Wayland e X11, já que só conversa com o servidor de áudio e com o MPRIS.
