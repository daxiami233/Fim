import { ArkAssignStmt, ArkClass, ArkMethod, Constant, FileSignature, Local, Scene, Value, ArkNormalBinopExpr, DefUseChain, Stmt, ArkInstanceInvokeExpr, ArkInstanceFieldRef, ClassSignature, ArkField } from "../../arkanalyzer/src";

// export class MyValue{
//     historyVals:Value[] = [];
//     value:any;
//     isFinish: boolean = false;
// }

export default class ValueAnalyzer {

    static getDefStmt(stmt: Stmt, chains: DefUseChain[], variable: Value) {
        if (variable instanceof Local || variable instanceof ArkInstanceFieldRef) {
            let workList: Array<Stmt> = []
            for (let chain of chains) {
                if (chain instanceof DefUseChain) {
                    if (chain.use == stmt) {
                        if (chain.def instanceof ArkAssignStmt) {
                            let leftOp = chain.def.getLeftOp();
                            if (variable instanceof Local) {
                                if (leftOp instanceof Local && leftOp.getName() == variable.getName())
                                    return chain.def;
                            }
                            if (variable instanceof ArkInstanceFieldRef) {
                                if (leftOp instanceof ArkInstanceFieldRef && 
                                    leftOp.getFieldSignature() == variable.getFieldSignature() &&
                                    leftOp.getBase() == variable.getBase()) 
                                    return chain.def;
                            }
                        } else {
                        }
                        if (!workList.includes(chain.def) && stmt != chain.def) {
                            workList.push(chain.def);
                        }
                    }
                }
            }
            let defStmt: ArkAssignStmt | undefined;
            for (let newStmt of workList) {
                let res  = this.getDefStmt(newStmt, chains, variable);
                if (res != undefined)  defStmt = res;
            }
            return defStmt;
        }
    }

    static getThisDefStmt(stmt: Stmt, chains: DefUseChain[], variable: ArkInstanceFieldRef, scene: Scene) {
        let fieldSig = variable.getFieldSignature();
        let clazzSig = fieldSig.getDeclaringSignature();
        if (clazzSig instanceof ClassSignature) {
            let clazz = scene.getClass(clazzSig);
            let field = clazz?.getField(fieldSig);
            let thisDefStmt = field?.getInitializer()[0];
            if (thisDefStmt instanceof ArkAssignStmt)
                return thisDefStmt;
        }
    }

    static getValue(stmt: Stmt, chains: DefUseChain[], variable: Value, scene: Scene) : string | undefined {
        if (variable instanceof Constant) return variable.getValue().toString();
        let defStmt = this.getDefStmt(stmt, chains, variable);
        if (defStmt == undefined && variable instanceof ArkInstanceFieldRef)
            defStmt = this.getThisDefStmt(stmt, chains, variable, scene);
        if (defStmt instanceof ArkAssignStmt) {
            let rightOp = defStmt.getRightOp()
            if (rightOp instanceof Constant) return rightOp.getValue().toString();
            if (rightOp instanceof Local) {
                return this.getValue(defStmt, chains, rightOp, scene);
            }
            if (rightOp instanceof ArkInstanceFieldRef) {
                return this.getValue(defStmt, chains, rightOp, scene);
            }
            if (rightOp instanceof ArkNormalBinopExpr) {
                if (rightOp.getOperator() == '+') {
                    let value1 =  this.getValue(defStmt, chains, rightOp.getOp1(), scene);
                    let value2 =  this.getValue(defStmt, chains, rightOp.getOp2(), scene);
                    if (value1 == undefined || value2 == undefined) return undefined;
                    return value1 + value2;
                }
            }
            if (rightOp instanceof ArkInstanceInvokeExpr) {
                let base = rightOp.getBase()
                if (base instanceof Local) return this.getValue(defStmt, chains, base, scene);
            }
        }
    }
}