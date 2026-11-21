# Regenerates the README demo. From the repo root:
#   PERSONAL_VAULT_HOME=/tmp/pv-demo uv run personal-vault index --path demo/notes --name demo
#   vhs demo/demo.tape
#   ffmpeg -y -i demo/raw.gif -vf "crop=1100:782:0:198,split[a][b];[a]palettegen[p];[b][p]paletteuse" demo/demo.gif
# The crop removes the Claude Code start banner, which shows the account's email.
# Needs: vhs, ffmpeg, claude, uv, Ollama with bge-m3.
Output demo/raw.gif

Require claude
Set Shell zsh
Set FontSize 15
Set Width 1100
Set Height 980
Set Padding 16
Set TypingSpeed 80ms
Set PlaybackSpeed 2.0

Hide
Type "cd demo/notes && export PERSONAL_VAULT_HOME=/tmp/pv-demo && unset $(env | grep -o '^CLAUDE[A-Z_]*') && clear"
Enter
Type `claude --setting-sources project --plugin-dir ../.. --permission-mode default --allowedTools "Bash(command -v uv)" "Bash(uv run:*)"`
Enter
Sleep 8s
Enter
Sleep 3s
Ctrl+L
Sleep 2s
Show

Sleep 1s
Type "/personal-vault:ask where does TLS end behind a load balancer?"
Sleep 2s
Enter
Sleep 34s
