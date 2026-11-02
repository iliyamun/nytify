using TS3AudioBot.Config;
using TS3AudioBot.CommandSystem;
using TS3AudioBot.ResourceFactories;

// Exercise the plugin against the real engine types, without connecting to a server.
var commands = CommandManager.GetBotCommands(null, typeof(MusicBot)).ToArray();
var rights = commands.Select(command => command.RequiredRight).ToArray();
foreach (var right in new[] { "cmd.music", "cmd.enqueue", "cmd.resume", "cmd.queue" })
    if (!rights.Contains(right)) throw new Exception("Command was not registered: " + right);

using var resources = new ResourceResolver(new ConfFactories());
using var plugin = new MusicBot(resources);
plugin.Initialize();
var context = new ResolveContext(resources, new ConfBot());
var result = await context.Load("Artist Song With Spaces", "music");
if (result.AudioResource.ResourceTitle != "Integration Test"
    || result.PlayUri != "/tmp/integration-audio.webm")
    throw new Exception("Resolver bridge returned unexpected data");
Console.WriteLine("Plugin commands registered; resolver subprocess and JSON bridge passed.");
