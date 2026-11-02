using System.Diagnostics;
using System.Text.Json;
using TS3AudioBot;
using TS3AudioBot.Audio;
using TS3AudioBot.CommandSystem;
using TS3AudioBot.Plugins;
using TS3AudioBot.Playlists;
using TS3AudioBot.ResourceFactories;

// The voice protocol, identity, queue and Opus transport are provided by TS3AudioBot.
public sealed class MusicBot : ICorePlugin
{
    private readonly ResourceResolver resources;
    private readonly MusicResolver resolver = new MusicResolver();
    public MusicBot(ResourceResolver resources) { this.resources = resources; }
    public void Initialize() => resources.AddResolver(resolver);
    public void Dispose() => resources.RemoveResolver(resolver);

    [Command("music")]
    [Usage("<song name or link>", "Play a YouTube link, Spotify track link, or song name.")]
    public static Task Music(PlayManager player, InvokerData invoker, string query)
        => player.Play(invoker, query, "music");

    [Command("enqueue")]
    [Usage("<song name or link>", "Add a song to the queue; starts playback if idle.")]
    public static Task Enqueue(PlayManager player, PlaylistManager queue, InvokerData invoker, string query)
    {
        if (queue.CurrentList.Items.Count >= 100)
            throw new CommandException("The queue has 100 songs. Use !clear before adding more.");
        return player.Enqueue(invoker, query, "music");
    }

    [Command("queue")]
    public static string Queue(PlaylistManager queue)
    {
        if (queue.CurrentList.Items.Count == 0) return "The queue is empty.";
        int start = Math.Max(0, queue.Index);
        return string.Join(" | ", queue.CurrentList.Items.Skip(start).Take(10)
            .Select((item, i) => (start + i + 1) + ". " + item));
    }

    [Command("resume")]
    public static void Resume(Player player) => player.Paused = false;

    // Private so the plugin loader sees exactly one exported plugin type.
    private sealed class MusicResolver : IResourceResolver
    {
        public string ResolverFor => "music";
        public void Dispose() { }
        private static readonly SemaphoreSlim Gate = new SemaphoreSlim(1);
        public MatchCertainty MatchResource(ResolveContext ctx, string uri)
            => MatchCertainty.OnlyIfLast;
        public string RestoreLink(ResolveContext ctx, AudioResource resource) => resource.ResourceId;
        public Task<PlayResource> GetResourceById(ResolveContext ctx, AudioResource resource)
            => GetResource(ctx, resource.ResourceId);

        public async Task<PlayResource> GetResource(ResolveContext ctx, string uri)
        {
            // Bound concurrent downloads and report busy rather than accumulating work.
            if (!await Gate.WaitAsync(0))
                throw new CommandException("Another song is loading. Try again in a moment.");
            try
            {
                var script = Environment.GetEnvironmentVariable("MUSIC_RESOLVER")
                    ?? "/app/musicbot/resolver.py";
                var start = new ProcessStartInfo(
                    Environment.GetEnvironmentVariable("MUSIC_PYTHON") ?? "python3")
                {
                    UseShellExecute = false,
                    RedirectStandardInput = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                };
                start.ArgumentList.Add(script);
                using var process = Process.Start(start)
                    ?? throw new CommandException("Could not start the music resolver.");
                // User input is data on stdin, never shell syntax or process arguments.
                await process.StandardInput.WriteAsync(uri);
                process.StandardInput.Close();
                var stdout = process.StandardOutput.ReadToEndAsync();
                var stderr = process.StandardError.ReadToEndAsync();
                using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(185));
                try { await process.WaitForExitAsync(timeout.Token); }
                catch (OperationCanceledException)
                {
                    process.Kill(entireProcessTree: true);
                    await process.WaitForExitAsync();
                    throw new CommandException("Song loading timed out. Try a different recording.");
                }
                var output = await stdout;
                await stderr; // Drain both pipes even on failure.
                if (process.ExitCode != 0)
                {
                    string message = "Could not load that song. Try another link or song name.";
                    try { message = JsonDocument.Parse(output).RootElement.GetProperty("error").GetString() ?? message; }
                    catch (JsonException) { }
                    throw new CommandException(message);
                }
                using var json = JsonDocument.Parse(output);
                var root = json.RootElement;
                return new PlayResource(root.GetProperty("path").GetString()!,
                    new AudioResource(root.GetProperty("source").GetString()!,
                        root.GetProperty("title").GetString()!, ResolverFor));
            }
            finally { Gate.Release(); }
        }
    }
}
