typedef unsigned __int8 uint8_t;
typedef unsigned __int16 uint16_t;
typedef unsigned __int32 uint32_t;
typedef unsigned __int64 uint64_t;
typedef __int64 intptr_t;
typedef unsigned __int64 uintptr_t;
typedef unsigned __int64 size_t;
typedef void(*Il2CppMethodPointer)();

struct MethodInfo;
struct Il2CppClass;

struct VirtualInvokeData {
    Il2CppMethodPointer methodPtr;
    const MethodInfo* method;
};

struct Il2CppClass_1 {
    const char* name;
};

struct Il2CppClass_2 {
    uint16_t method_count;
};

union Il2CppRGCTXData {
    void* rgctxDataDummy;
    const MethodInfo* method;
    Il2CppClass* klass;
};

struct Il2CppClass {
    Il2CppClass_1 _1;
    void* static_fields;
    Il2CppRGCTXData* rgctx_data;
    Il2CppClass_2 _2;
    VirtualInvokeData vtable[255];
};

typedef void (*InvokerMethod)(Il2CppMethodPointer, const MethodInfo*, void*, void**, void*);

struct MethodInfo {
    Il2CppMethodPointer methodPointer;
    InvokerMethod invoker_method;
    const char* name;
    Il2CppClass *klass;
    union {
        const Il2CppRGCTXData* rgctx_data;
        const void* methodMetadataHandle;
    };
    uint32_t token;
};

struct UnityEngine_Object_Fields {
    intptr_t m_CachedPtr;
};
struct UnityEngine_Component_Fields {
    UnityEngine_Object_Fields super;
};
struct UnityEngine_Behaviour_Fields {
    UnityEngine_Component_Fields super;
};
struct UnityEngine_MonoBehaviour_Fields {
    UnityEngine_Behaviour_Fields super;
    struct System_Threading_CancellationTokenSource_o* m_CancellationTokenSource;
};
struct Mono_ValueTuple_T1__T2__Fields {
    void* Item1;
    void* Item2;
};

struct UnityEngine_UIElements_BaseUxmlFactory_TCreatedType__TTraits__Fields {
    void* placeholder;
};
struct UnityEngine_UIElements_UxmlFactory_UnsignedIntegerField__UnsignedIntegerField_UxmlTraits__Fields {
    UnityEngine_UIElements_BaseUxmlFactory_TCreatedType__TTraits__Fields super;
};
struct UnityEngine_UIElements_UnsignedIntegerField_UxmlFactory_Fields {
    UnityEngine_UIElements_UxmlFactory_UnsignedIntegerField__UnsignedIntegerField_UxmlTraits__Fields super;
};
struct UnityEngine_UIElements_UxmlUnsignedIntAttributeDescription___c_Fields {
};


struct UnityEngine_Color_Fields {
    float r;
    float g;
    float b;
    float a;
};
struct UnityEngine_Color_o {
    UnityEngine_Color_Fields fields;
};
struct UnityEngine_Vector3_Fields {
    float x;
    float y;
    float z;
};
struct UnityEngine_Vector3_o {
    UnityEngine_Vector3_Fields fields;
};
struct initializer_Fields {
    UnityEngine_MonoBehaviour_Fields super;
    struct UnityEngine_Color_o styleDeepBlue;
    struct UnityEngine_Vector3_o buttonStartScale;
};
struct initializer_c {
    Il2CppClass_1 _1;
};
struct initializer_o {
    initializer_c *klass;
    void *monitor;
    initializer_Fields fields;
};
