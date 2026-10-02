# مراجعة وتطوير Atlas_AI_Annoation

التاريخ: 2026-10-02. [المستودع](https://github.com/aymank2020/Atlas_AI_Annoation).
كان المستودع فارغًا بلا commits أو runtime. أصبحت المرحلة الأولى نواة قابلة
للتشغيل لفحص لقطات المقاطع محليًا، بمصدر محدد من مستودع المستخدم المختبر.

## نتيجة المراجعة والقرار

إنشاء نسخة كاملة أخرى من تطبيق Atlas القديم سيكرر workers وإعدادات جلسات
ومسارات متناقضة. لذلك اختير `atlas_hetzner_final_project` كنواة، لأنه اجتاز
353 اختبارًا و1skipped ثم20 فحصًا مركّزًا، بينما نسخة المشروع الأقدم تتعطل
عند جمع جميع الاختبارات بسبب حزمة مفقودة. مصدر الاستخراج commit
`19c1f9c06e3b04b940f55bcc7b7d306d77fe0fb1` والملف SHA256 موثقان في
[PROVENANCE.md](../PROVENANCE.md).

## خطة المرحلة الأولى المنفذة

1. P1 — استخراج snapshot guard الفعلي الذي يمنع التطابق الزائف للقطات
   NaN/Infinity/فارغة/مكررة أو ذات مدة غير صالحة: منفذ في
   [snapshots.py](../atlas_annotation/snapshots.py).
2. P1 — CLI يقرأ JSON ويخرج قرارًا واضحًا وexit0/1/2 ويحافظ على مرجعية DOM
   والمصدر، مع AI time مجرد تحذير: منفذ في [cli.py](../atlas_annotation/cli.py).
3. P1 — منع tolerance غير محدودة أو سالبة في CLI وفي library العامة:
   منفذ، كي لا تتجاوز NaN مقارنة drift.
4. P2 — package دون تبعيات runtime، console script وأمثلة وعشرة اختبارات
   offline وworkflowPython3.11–3.14: منفذ. تشغيل CI خارجيًا غير متحقق بعد.

## التحقق الفعلي

- `python -m unittest discover -s tests -v`: **10 اختبارات ناجحة**، مع حالات
  فرعية لقيم/حقول متعددة. معظمها يشغل `python -m atlas_annotation` كعملية
  مستقلة؛ لا mock داخلي لمنطق البناء أو الاتساق.
- أمر الأمثلة مع `--plan examples/ai-plan.json`: exit0، checksum متطابقان،
  warning لاختلاف مدةAI99 ثانية عنDOM4 ثوانٍ، وsubmit_authorized=false.
- `python -m pip install --no-build-isolation --no-deps --no-cache-dir --target
  D:\Codex-GitHub-Review-20261002\atlas-core-final-install .`: بناء wheel
  وتثبيت0.1.0 ناجحان دون تنزيل تبعيات.
- تشغيل executable المثبت `bin/atlas-annotation.exe` من خارج جذر المصدر،
  مع PYTHONPATH لمسار التثبيت والأمثلة المطلقة: **exit0 وJSONok=true**.
  هذا يثبت console entrypoint والتغليف، وليس مجرد import من working directory.
- راجعت diff مقابل الملف الأصلي: اختلاف وصف المنشأ وفحص tolerance فقط في
  snapshot core. git diff --check نجح بعد staging.

## فحص التكامل والأثر

قرئت مهارة Integration & Impact Review بعد مراجعة الكود والاختبارات.
`python -m atlas_annotation` → `__main__.py` → `cli.main` → قراءة البنية →
`build_segment_snapshot` → `compare_segment_snapshots` → JSON وexit status.
المستهلك الثاني `[project.scripts]` → executable wheel → cli.main؛ شغّلته
من مسار خارجي. فصل هذا الربط يجعل اختبارات CLI تفشل لأنها تتحقق من نتائج
النواة بالفعل، لا من استدعاء helper وهمي.

لم توجد callers قديمة في المستودع الفارغ. وظائف snapshot والـAI warnings
المستخلصة محفوظة، لا aliases للمتصفح أو تبعيات خارجية. مخرجات الفحص تصرح
scope=snapshot_integrity وsubmit_authorized=false؛ صحة التوقيت المحلية
لا تفوض إرسالًا ولا تثبت جودة التسمية.

## الفجوات وخطة التوحيد اللاحقة

1. P1 — توثيق عقد exports ومهايئات Windows/Linux وإعادة الاستخراج، مع fixtures
   مناسبة لكل نظام؛ غير منفذ.
2. P2 — ترحيل adapters اللازمة من النسخ الموجودة وواجهة مراجعة محلية واختبارات
   e2e، دون نسخ شجرة legacy كاملة؛ غير منفذ.
3. P1 — إثبات بوابة الإرسال وعدم خلط محادثات Gemini في بيئة اختبار مخصصة قبل
   تشغيل اتصال خارجي؛ غير منفذ. لا browser/server/session أو credentials
   أو بيانات إنتاج في هذه المرحلة. لم تُدقق جودة labels أو كل قواعد الحلقة.
4. CI وPython3.12–3.14/Linux لم تُشغّل هنا؛ التحقق المحلي علىWindows/Python3.11.9.

## البحث المستخدم

- [Python JSON](https://docs.python.org/3.11/library/json.html): التحويل الافتراضي
  يسمح NaN/Infinity، لذلك تطابق checksum لا يثبت صلاحية رقمية.
- [Python math.isfinite](https://docs.python.org/3/library/math.html#math.isfinite):
  أساس حارس الأزمنة والسماحية.
- [actions/checkout](https://github.com/actions/checkout) و
  [actions/setup-python](https://github.com/actions/setup-python): workflow
  يستخدم الإصدارات الحاليةv7 وcontents:read وpersist-credentials:false؛ هذا
  إعداد تم فحصه من المصدر الرسمي، لا ادعاء نجاح تشغيل GitHub.

اكتملت خطة المرحلة الأولى أعلاه فقط. تجميع تطبيق Atlas كامل وترحيل المستخدمين
والنشر مراحل مستقلة موثقة وليست نتيجة هذه النواة المحلية.
