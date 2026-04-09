#ifndef W_INPUT_INCLUDED
#define W_INPUT_INCLUDED

// Struct GPU partagée — miroir exact du C# WaterInteractor (stride 16 bytes)
// float2 position : world XZ
// float  age      : secondes depuis création (calculé côté C# avant upload)
// int    isImpact : 1 = impact bref (pied levé), 0 = persistant (pied posé)
struct WaterInteractor
{
    float2 position;
    float  age;
    int    isImpact;
};

#endif
