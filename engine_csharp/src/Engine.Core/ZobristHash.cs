namespace Engine.Core;

internal static class ZobristHash
{
    public static ulong Compute(string normalizedFenKey)
    {
        const ulong offsetBasis = 14695981039346656037UL;
        const ulong prime = 1099511628211UL;

        ulong hash = offsetBasis;
        foreach (var character in normalizedFenKey)
        {
            hash ^= character;
            hash *= prime;
        }

        return hash;
    }
}
