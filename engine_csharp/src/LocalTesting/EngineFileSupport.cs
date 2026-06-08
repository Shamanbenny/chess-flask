using System.Text.RegularExpressions;
using Engine.Core;

internal static partial class EngineFileSupport
{
    public static EngineVersions.ResolvedEngineFile ResolveV3PlusEngine(string engineFilePath)
    {
        var engine = EngineVersions.ResolveTimeLimitedEngineFromFilePath(engineFilePath);
        if (!IsV3PlusEngineStem(engine.EngineStem))
        {
            throw new ArgumentException(
                $"LocalTesting only supports V3+ engine files. Received '{engine.EngineStem}' from {engine.SourcePath}.");
        }

        return engine;
    }

    private static bool IsV3PlusEngineStem(string engineStem)
    {
        var match = EngineStemRegex().Match(engineStem);
        return match.Success
            && int.TryParse(match.Groups["major"].Value, out var major)
            && major >= 3;
    }

    [GeneratedRegex("^V(?<major>\\d+)_\\d+Engine$", RegexOptions.CultureInvariant)]
    private static partial Regex EngineStemRegex();
}
