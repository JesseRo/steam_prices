
// Provide a default path to dwr.engine
if (dwr == null) var dwr = {};
if (dwr.engine == null) dwr.engine = {};
if (DWREngine == null) var DWREngine = dwr.engine;

if (TmpService == null) var TmpService = {};
TmpService._path = '/dwr';
TmpService.fetchData = function(p0, p1, p2, p3, p4, p5, callback) {
  dwr.engine._execute(TmpService._path, 'TmpService', 'fetchData', p0, p1, p2, p3, p4, p5, callback);
}
