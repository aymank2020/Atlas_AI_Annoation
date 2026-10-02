# البحث الأولي لواجهة المراجعة المحلية

المراجع قُرئت من أصحابها في 2 أكتوبر 2026، باستخدام مهارة research في مسار
الوكيل الحالي. النتائج أدناه تشرح اختيارات التنفيذ؛ لا تثبت قبولًا من Atlas.

1. [Python JSON](https://docs.python.org/3.11/library/json.html): فك JSON الافتراضي
   يقبل NaN وInfinity، ونجاح فك النص لا يثبت أن الأزمنة محدودة. لذلك تنقل
   الواجهة نص الملف داخل string، ثم يفسره Python ويمرره إلى الحارس المستخلص.
   لا JSON.parse للملفات في JavaScript ولا تحويل NaN إلى null قبل الفحص.
   المدخل مقيد بالحجم وعدد المقاطع، وخطأ العمق المتداخل يعاد كخطأ إدخال.
   التقارير تستخدم allow_nan=False، وتحفظ القيم غير الصالحة في خلايا نصية.
2. [math.isfinite](https://docs.python.org/3/library/math.html#math.isfinite):
   يميز العدد المحدود من NaN واللانهاية. النواة الحالية تطبقه على الأزمنة
   والسماحية. أبقينا هذه النواة دون تغيير، ولم نضع حارسًا بديلًا في الواجهة.
3. [http.server](https://docs.python.org/3.11/library/http.server.html): يوفر
   HTTPServer وBaseHTTPRequestHandler لتنفيذ الخادم المحلي. صممنا ثلاثة
   مسارات موارد ثابتة ومسار POST واحدًا بدل استخدام تقديم مجلد كامل.
   الربط 127.0.0.1 فقط، وحدود الجسم والملف وHost/Origin والمهلة اختيارات
   صريحة لهذا التطبيق المحلي. لا CORS أو مسار يقرأ filename من HTTP.
4. [importlib.resources](https://docs.python.org/3.11/library/importlib.resources.html):
   يسمح بقراءة موارد الحزمة عبر files دون افتراض أن cwd هو checkout.
   لذلك تُدرج HTML/JS/CSS ضمن wheel ويقرأها الخادم من الحزمة المثبتة.
   اختبار console المثبت من مجلد آخر يفحص هذه الموارد وقرار POST فعليًا.
5. [MDN TextDecoder.ignoreBOM](https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder/ignoreBOM)
   و[File API](https://developer.mozilla.org/en-US/docs/Web/API/File_API/Using_files_from_web_applications):
   القراءة من ArrayBuffer مع UTF-8 وفحص الترميز تحفظ BOM داخل النص المنقول.
   SHA256 يشمل BOM ونهايات الأسطر؛ فك المهايئ يزيل BOM واحدًا فقط عند parsing.
   القراءة وحساب بصمة الملف لا يعيدان كتابة الملف الذي اختاره المستخدم.

الفحص المحلي يثبت سلامة اللقطات واتساقها ضمن السماحية. جودة التسمية وهوية
الحلقة والتفويض بالإرسال تتطلب عقودًا أخرى؛ submit_authorized يبقى false.
